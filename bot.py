# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat

# Windows uchun asyncio policy (agar kerak bo'lsa)
try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except Exception:
    pass

# ========== SOZLAMALAR ==========
api_id = 28023612
api_hash = 'fe94ef46addc1b6b8253d5448e8511f0'

# Bu yerga topilgan e'lonlar yuboriladigan kanal/guruh linkingizni qo'ying
TARGET_CHAT = 'https://t.me/+BFl15wH-PAswZTYy'

# Bir vaqtda yuborilayotgan send_message so'rovlarini cheklash (telegr. rate-limit uchun)
SEND_SEMAPHORE_LIMIT = 10

# To'liq kalit so'zlar ro'yxati (hozircha keng ro'yxat)
KEYWORDS = [
    # odam bor
    'odam bor', 'odambor', 'odam bor ekan', 'odam bor edi', 'odam borakan',
    'bitta odam bor', 'ikkita odam bor', 'uchta odam bor', "to'rtta odam bor", 'tortta odam bor',
    'komplek odam bor', 'komplekt odam bor', 'kompilek odam bor', 'kampilek odam bor',
    '1ta odam bor', '2ta odam bor', '3ta odam bor', '4ta odam bor',
    'odam bor 1', 'odam bor 2', 'odam bor 3', 'odam bor 4',
    'rishtonga odam bor', 'toshkentga odam bor', "toshkendan farg'onaga odam bor",
    'тўрта одам бор', 'одам бор', 'комплект одам бор', 'компилект odam бор', 'кампилек одам бор',

    # mashina kerak
    'mashina kerak', 'mashina kere', 'mashina kerek', 'mashina kera', 'mashina keraa',
    'bagajli mashina kerak', 'bosh mashina kerak', 'bosh mashina bormi', 'boshi bormi',
    'машина керак', 'багажли машина керак', 'бош машина керак', 'машина кере', 'машина кераа',

    # pochta bor
    'pochta bor', 'pochta kerak', 'pochta ketadi', 'pochta olib ketadi', 'pochta bormi',
    'почта бор', 'почта кетади', 'почта керак', 'почта олиб кетади',
    'тошкентга почта бор', 'тошкентдан почта бор', 'риштонга почта бор', 'риштондан почта бор',

    # ketadi
    'ketadi', 'ketvotti', 'ketayapti', 'ketishadi', 'ketishi kerak', 'hozir ketadi',
    'кетяпт', 'кетвотди', 'кетади', 'кетишади', 'кетиши керак',

    # dostavka
    'dastavka bor', 'dostavka bor', 'dastafka', 'dastafka bor',
    'доставкa бор', 'даставка бор', 'доставка бор', 'доставкa керак'
]

# Precompile regexlar
KEYWORDS_RE = re.compile(r"|".join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)

# Elastik telefon kandidate regex (turli formatlarni qamrab oladi)
PHONE_CANDIDATE_RE = re.compile(
    r'(\+?998[\d\-\s\(\)]{9,15}|\b9[\d\-\s\(\)]{8,13}\b|\b998[\d\-\s\(\)]{9,13}\b)'
)

# Telegram client
client = TelegramClient('taxi_ultrafast', api_id, api_hash)

# Semaphore send limit
send_semaphore = asyncio.Semaphore(SEND_SEMAPHORE_LIMIT)


# ========== yordamchi funktsiyalar ==========
def normalize_phone(raw: str) -> str | None:
    """
    raw: candidate string (may contain +, spaces, dashes, parentheses)
    Returns standardized +998XXXXXXXXX or None
    """
    if not raw:
        return None
    digits = re.sub(r'\D', '', raw)  # faqat sonlarni qoldiramiz
    # 1) 998XXXXXXXXX -> +998XXXXXXXXX
    if digits.startswith('998') and len(digits) >= 12:
        return f"+{digits[:12]}"
    # 2) +998XXXXXXXXX handled by above after stripping
    # 3) 9XXXXXXXX -> +9989XXXXXXXX
    if len(digits) == 9 and digits.startswith('9'):
        return f"+998{digits}"
    # 4) 0XXXXXXXXX (kam uchraydi) -> treat as local and convert
    if len(digits) == 9 and digits.startswith('0'):
        return f"+998{digits[1:]}"
    # 5) if digits len == 12 and startswith 998
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    # 6) sometimes 11 or 10 length: try to salvage last 9 digits
    if len(digits) > 9:
        last9 = digits[-9:]
        if last9.startswith('9'):
            return f"+998{last9}"
    return None


async def safe_send_message(chat, text, parse_mode='html'):
    """
    Semaphore bilan xavfsiz yuborish: bir vaqtning o'zida SEND_SEMAPHORE_LIMIT dan ortiq send bo'lmaydi.
    Bu Telegram rate-limit xavfini kamaytiradi.
    """
    async with send_semaphore:
        return await client.send_message(chat, text, parse_mode=parse_mode)


# ========== asosiy logic ==========
@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):
    """
    Handler juda tez qaytadi: har bir yangi xabar uchun alohida task yaratadi.
    Task ichida esa send_message await qilinadi (shuning uchun yuborish kechikmaydi).
    """
    try:
        # darhol task yaratamiz (handler block qilinmaydi)
        asyncio.create_task(process_message(event))
    except Exception as e:
        print("❌ Task yaratishda xato:", e)


async def process_message(event):
    try:
        # Faqat guruh/kanal xabarlari (private xabarlarni o'tkazamiz)
        if not isinstance(event.peer_id, (PeerChannel, PeerChat)):
            return

        text = event.raw_text or ""
        if not text.strip():
            return

        # Faqat kalit so'z bo'lsa davom etamiz
        if not KEYWORDS_RE.search(text):
            return

        # Chat va sender ma'lumotlarini parallel olamiz
        chat_task = asyncio.create_task(event.get_chat())
        sender_task = asyncio.create_task(event.get_sender())
        chat, sender = await asyncio.gather(chat_task, sender_task)

        # Guruh nomi va link (agar username bo'lsa to'liq link)
        group_name = getattr(chat, 'title', None) or "Noma'lum guruh"
        if getattr(chat, 'username', None):
            group_link = f"https://t.me/{chat.username}/{event.id}"
        else:
            group_link = group_name  # username yo'q bo'lsa faqat nomini ko'rsatamiz

        # Habar egasi (username yoki Berkitilgan)
        username = getattr(sender, 'username', None)
        if username:
            haber_egasi = f"@{username}"
        else:
            # agar sender.first_name mavjud bo'lsa, kichik ko'rsatish variantini ham qo'yish mumkin
            haber_egasi = "Berkitilgan"

        # Maxsus profil link (tg://user?id=...) yoki Berkitilgan
        sender_id = getattr(sender, 'id', None)
        if sender_id:
            profile_link_html = f"<a href='tg://user?id={sender_id}'>Profilga o‘tish</a>"
        else:
            profile_link_html = "Berkitilgan"

        # Telefonni aniqlash — bir nechta strategiya:
        phone = None
        # 1) PHONE_CANDIDATE_RE bilan qidiramiz (eng aniq)
        for m in PHONE_CANDIDATE_RE.finditer(text):
            cand = m.group(0)
            normalized = normalize_phone(cand)
            if normalized:
                phone = normalized
                break

        # 2) agar yuqorida topilmasa, matndan 9+ ketma-ket raqamlarni izlaymiz
        if not phone:
            all_digits = re.findall(r'\d{9,12}', re.sub(r'\D', '', text))  # bu qator bir oz fallback
            # Eslatma: yuqoridagi satr text ni butunlay faqat raqamlarga aylantirib, unda ketma-ket raqamlarni oladi
            if all_digits:
                for seq in all_digits:
                    normalized = normalize_phone(seq)
                    if normalized:
                        phone = normalized
                        break

        # 3) fallback: agar hali ham yo'q bo'lsa "Raqam berkitilgan"
        phone_display = phone if phone else "Raqam berkitilgan"

        # Xabarni shakllantirish (siz so'ragan formatga mos)
        # Guruh: name — link (agar link bo'lsa)
        group_line = f"{group_name}"
        if getattr(chat, 'username', None):
            group_line = f"{group_name} — {group_link}"
        else:
            group_line = f"{group_name} — {group_link}"

        message_text = (
            f"🚖 <b>Xabar topildi!</b>\n\n"
            f"📄 <b>Matn:</b>\n{text}\n\n"
            f"📍 <b>Guruh:</b> {group_line}\n\n"
            f"👤 <b>Habar egasi:</b> {haber_egasi}\n\n"
            f"📞 <b>Raqam:</b> {phone_display}\n\n"
            f"🔗 <b>Maxsus link:</b> {profile_link_html}\n\n"
            f"🔔 Yangi e’lonlardan xabardor bo‘ling!"
        )

        # Juda tez yuborish: KAFOLAT bilan yuboriladi (await qilinadi)
        try:
            await safe_send_message(TARGET_CHAT, message_text, parse_mode='html')
            print(f"✅ Yuborildi: {group_name} | user: {haber_egasi} | phone: {phone_display}")
        except Exception as send_err:
            # Agar yuborishda xato bo'lsa konsolga chiqaramiz
            print("❌ Yuborishda xatolik:", send_err)

    except Exception as e:
        print("❌ process_message xatolik:", e)


# ========== ishga tushirish ==========
if __name__ == "__main__":
    print("🚕 ULTRA FAST Taxi Bot (v2) ishga tushdi! Faqat yangi xabarlar, juda tez yuboradi ⚡")
    client.start()
    client.run_until_disconnected()