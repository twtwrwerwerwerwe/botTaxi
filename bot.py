# -*- coding: utf-8 -*-
import re
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat

# Windows uchun asyncio policy
try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except Exception:
    pass

# ========== SOZLAMALAR ==========
api_id = 28023612
api_hash = 'fe94ef46addc1b6b8253d5448e8511f0'

# Bu yerga topilgan e'lonlar yuboriladigan kanal/guruh linkingizni qo'ying
TARGET_CHAT = 'https://t.me/+BFl15wH-PAswZTYy'

# To'liq kalit so'zlar ro'yxati
KEYWORDS = [
    # odam bor
    'odam bor', 'odambor', 'odam bor ekan', 'odam bor edi', 'odam borakan',
    'bitta odam bor', 'ikkita odam bor', 'uchta odam bor', "to'rtta odam bor", 'tortta odam bor',
    'komplek odam bor', 'komplekt odam bor', 'kompilek odam bor', 'kampilek odam bor',
    '1ta odam bor', '2ta odam bor', '3ta odam bor', '4ta odam bor',
    'odam bor 1', 'odam bor 2', 'odam bor 3', 'odam bor 4',
    'rishtonga odam bor', 'toshkentga odam bor', "toshkendan farg'onaga odam bor",
    'тўрта одам бор', 'одам бор', 'комплект одам бор', 'компилект одам бор', 'кампилек одам бор',

    # mashina kerak
    'mashina kerak', 'mashina kere', 'mashina kerek', 'mashina kera', 'mashina keraa',
    'bagajli mashina kerak', 'bosh mashina kerak', 'bosh mashina bormi', 'boshi bormi',
    'mashina izlayapman', 'mashina topaman', 'mashina kerak edi',
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

# Regex tayyorlash
KEYWORDS_RE = re.compile(r"|".join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)

# Telefon raqamni aniqlash regexi
PHONE_RE = re.compile(r'(\+?\d[\d\-\s\(\)]{7,20}\d)')

# Telegram client
client = TelegramClient('taxi_ultrafast', api_id, api_hash)

# ========== yordamchi funksiyalar ==========
def normalize_phone(raw: str) -> str | None:
    """Raqamni +998XXXXXXXXX formatiga keltiradi"""
    if not raw:
        return None
    digits = re.sub(r'\D', '', raw)
    if len(digits) >= 9:
        if digits.startswith('998') and len(digits) >= 12:
            return '+' + digits[:12]
        if digits.startswith('0') and len(digits) == 9:
            return '+998' + digits[1:]
        if len(digits) == 9 and digits.startswith('9'):
            return '+998' + digits
        if len(digits) > 9:
            last9 = digits[-9:]
            return '+998' + last9
    return None

# ========== asosiy logic ==========
@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):
    try:
        text = event.raw_text or ""
        if not text.strip() or not KEYWORDS_RE.search(text):
            return

        chat_task = asyncio.create_task(event.get_chat())
        sender_task = asyncio.create_task(event.get_sender())
        chat, sender = await asyncio.gather(chat_task, sender_task)

        # Guruh nomi va link
        group_name = getattr(chat, 'title', 'Noma\'lum guruh')
        if getattr(chat, 'username', None):
            group_link = f"https://t.me/{chat.username}/{event.id}"
        else:
            group_link = group_name

        # Habar egasi
        username = getattr(sender, 'username', None)
        haber_egasi = f"@{username}" if username else "Berkitilgan"

        sender_id = getattr(sender, 'id', None)
        profile_link_html = f"<a href='tg://user?id={sender_id}'>Profilga o'tish</a>" if sender_id else "Berkitilgan"

        # Telefon raqam topish
        phone = getattr(sender, 'phone', None)
        if phone:
            phone = normalize_phone(str(phone))
        if not phone:
            for m in PHONE_RE.finditer(text):
                phone = normalize_phone(m.group(0))
                if phone:
                    break
        if not phone:
            phone = "Raqam berkitilgan"

        message_text = (
            f"🚖 <b>Xabar topildi!</b>\n\n"
            f"📄 <b>Matn:</b>\n{text}\n\n"
            f"📍 <b>Guruh:</b> {group_name} — {group_link}\n\n"
            f"👤 <b>Habar egasi:</b> {haber_egasi}\n\n"
            f"📞 <b>Raqam:</b> {phone}\n\n"
            f"🔗 <b>Profil link:</b> {profile_link_html}\n\n"
            f"🔔 Yangi e’lonlardan xabardor bo‘ling!"
        )

        # Xabar yuborish
        await client.send_message(TARGET_CHAT, message_text, parse_mode='html')
        print(f"✅ Yuborildi: {group_name} | {haber_egasi} | {phone}")

    except Exception as e:
        print("❌ Xatolik:", e)

# ========== ishga tushirish ==========
if __name__ == "__main__":
    print("🚕 ULTRA FAST Taxi Bot ishga tushdi! Faqat yangi xabarlar, juda tez yuboradi ⚡")
    client.start()
    client.run_until_disconnected()
