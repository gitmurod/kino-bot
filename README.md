# 🎬 Mukammal Telegram Kino Bot

Admin paneli, majburiy obuna, statistika va ko'p funksiyali bot.

---

## ⚙️ Sozlash (bot.py — 2 qator)

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # @BotFather dan
OWNER_ID  = 123456789               # Sizning Telegram ID (@userinfobot)
```

---

## 🚀 Ishga tushirish

```bash
pip install python-telegram-bot==20.7
python bot.py
```

---

## 🎛 Admin panel — /admin

### 📡 Kanallarni sozlash
- Kanal qo'shish: `kanal_id | Nomi | https://t.me/link`
- Kanalni yoqish/o'chirish (zayafka toggle)
- Kanal o'chirish
- Faol kanalga obuna bo'lmagan user kino ko'ra olmaydi

### 📊 Statistika
- Jami va bugungi foydalanuvchilar
- Jami kinolar soni
- Kinolar ro'yxati (sahifalangan, ko'rilishlar bilan)
- Har bir kinoni o'chirish tugmasi

### 📨 Xabar yuborish
- Barcha userlarga xabar yuborish
- Matn, rasm, video — istalgan format
- Yuborish jarayoni progress ko'rsatadi

### 🎬 Kino yuklash (bosqichma-bosqich)
1. Nomi
2. Yili
3. Janri
4. Reytingi
5. Tavsifi
6. Video fayl

### 🤖 Bot holati
- Foydalanuvchilar statistikasi
- Kinolar, kanallar, adminlar soni

### 👥 Adminlar (faqat egasi)
- Admin qo'shish (ID bo'yicha)
- Admin o'chirish

---

## 📁 Fayllar

| Fayl | Vazifasi |
|------|---------|
| `bot.py` | Asosiy bot kodi |
| `database.py` | SQLite baza |
| `movies.db` | Baza fayli (avtomatik) |
