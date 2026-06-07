import logging
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMemberMember, ChatMemberOwner, ChatMemberAdministrator
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
from telegram.error import TelegramError
from database import Database

# ════════════════════════════════════════════════
#  SOZLAMALAR
# ════════════════════════════════════════════════
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID  = int(os.environ.get("OWNER_ID"))
DB_PATH     = "movies.db"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
db = Database(DB_PATH)

# ConversationHandler statelari
(
    ST_MOVIE_TITLE, ST_MOVIE_YEAR, ST_MOVIE_GENRE,
    ST_MOVIE_RATING, ST_MOVIE_DESC, ST_MOVIE_VIDEO,
    ST_BROADCAST,
    ST_ADD_CHANNEL, ST_ADD_ADMIN, ST_REMOVE_ADMIN,
) = range(10)


# ════════════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ════════════════════════════════════════════════

def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid == OWNER_ID or db.is_admin(uid)

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Kanallarni sozlash", callback_data="panel_channels")],
        [InlineKeyboardButton("📊 Statistika",  callback_data="panel_stats"),
         InlineKeyboardButton("📨 Xabar yuborish", callback_data="panel_broadcast")],
        [InlineKeyboardButton("🎬 Kino yuklash", callback_data="panel_upload")],
        [InlineKeyboardButton("🤖 Bot holati",  callback_data="panel_botstatus"),
         InlineKeyboardButton("👥 Adminlar",   callback_data="panel_admins")],
    ])

async def check_subscription(bot, user_id) -> bool:
    """Foydalanuvchi majburiy kanallarga obuna bo'lganmi?"""
    channels = db.get_active_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch['channel_id'], user_id)
            if not isinstance(member, (ChatMemberMember, ChatMemberOwner, ChatMemberAdministrator)):
                return False
        except TelegramError:
            pass
    return True

async def subscription_prompt(update: Update, bot):
    channels = db.get_active_channels()
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(
            f"📢 {ch['title']}", url=ch['link']
        )])
    keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    await update.message.reply_text(
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ════════════════════════════════════════════════
#  FOYDALANUVCHI — /start & qidiruv
# ════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_user(user.id, user.username, user.full_name)

    if not await check_subscription(ctx.bot, user.id):
        await subscription_prompt(update, ctx.bot)
        return

    await update.message.reply_text(
        f"🎬 Salom, <b>{user.first_name}</b>!\n\n"
        "Kino nomini yozing — men sizga topib beraman.",
        parse_mode="HTML"
    )


async def check_sub_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_subscription(ctx.bot, q.from_user.id):
        await q.message.edit_text(
            "✅ Rahmat! Endi kino nomini yozing."
        )
    else:
        await q.answer("❌ Hali ham obuna bo'lmadingiz!", show_alert=True)


async def search_movie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_or_update_user(user.id, user.username, user.full_name)

    if not await check_subscription(ctx.bot, user.id):
        await subscription_prompt(update, ctx.bot)
        return

    query = update.message.text.strip()
    results = db.search_movies(query)

    if not results:
        await update.message.reply_text(
            f"😔 <b>'{query}'</b> topilmadi.\nBoshqa nom bilan urinib ko'ring.",
            parse_mode="HTML"
        )
        return

    if len(results) == 1:
        await deliver_movie(update, ctx, results[0])
    else:
        kb = [[InlineKeyboardButton(
            f"🎬 {m['title']} ({m['year']})", callback_data=f"movie_{m['id']}"
        )] for m in results[:10]]
        await update.message.reply_text(
            f"🔍 <b>'{query}'</b> bo'yicha {len(results)} ta natija:",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )


async def deliver_movie(update: Update, ctx: ContextTypes.DEFAULT_TYPE, movie: dict):
    chat_id = update.effective_chat.id
    caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"📅 Yil: {movie['year']}\n"
        f"🎭 Janr: {movie['genre']}\n"
        f"⭐ Reyting: {movie['rating']}\n"
    )
    if movie.get('description'):
        caption += f"\n📝 {movie['description']}"

    await ctx.bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
    if movie.get('file_id'):
        await ctx.bot.send_video(
            chat_id=chat_id, video=movie['file_id'],
            caption=f"🎬 {movie['title']}", supports_streaming=True
        )
    else:
        await ctx.bot.send_message(chat_id=chat_id, text="⚠️ Video hali yuklanmagan.")


async def movie_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    movie_id = int(q.data.split("_")[1])
    movie = db.get_movie_by_id(movie_id)
    if movie:
        await deliver_movie(update, ctx, movie)
    else:
        await q.message.reply_text("❌ Kino topilmadi.")


# ════════════════════════════════════════════════
#  ADMIN PANEL — /admin
# ════════════════════════════════════════════════

async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Ruxsat yo'q!")
        return
    await update.message.reply_text(
        "⚙️ <b>Admin panel</b>", parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


async def panel_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    if not is_admin(uid):
        await q.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await q.answer()
    data = q.data

    # ── Orqaga ──
    if data == "panel_main":
        await q.message.edit_text("⚙️ <b>Admin panel</b>", parse_mode="HTML",
                                   reply_markup=main_menu_kb())

    # ═══════════════════════════════════════════
    # 📡 KANALLARNI SOZLASH
    # ═══════════════════════════════════════════
    elif data == "panel_channels":
        await show_channels_panel(q)

    elif data == "ch_add":
        ctx.user_data['state'] = ST_ADD_CHANNEL
        await q.message.edit_text(
            "📡 <b>Yangi kanal qo'shish</b>\n\n"
            "Quyidagi formatda yuboring:\n"
            "<code>kanal_id | Kanal nomi | https://t.me/kanal</code>\n\n"
            "Misol:\n<code>-1001234567890 | Mening Kanalim | https://t.me/mening_kanalim</code>\n\n"
            "❌ Bekor: /cancel",
            parse_mode="HTML"
        )

    elif data.startswith("ch_toggle_"):
        ch_id = int(data.split("_")[2])
        chs = db.get_all_channels()
        ch = next((c for c in chs if c['id'] == ch_id), None)
        if ch:
            db.toggle_channel(ch_id, 0 if ch['active'] else 1)
        await show_channels_panel(q)

    elif data.startswith("ch_del_"):
        ch_id = int(data.split("_")[2])
        db.delete_channel(ch_id)
        await show_channels_panel(q)

    # ═══════════════════════════════════════════
    # 📊 STATISTIKA
    # ═══════════════════════════════════════════
    elif data == "panel_stats":
        await show_stats_panel(q)

    elif data == "stats_movies":
        await show_movies_list(q)

    elif data.startswith("stats_page_"):
        page = int(data.split("_")[2])
        await show_movies_list(q, page)

    # ═══════════════════════════════════════════
    # 📨 XABAR YUBORISH
    # ═══════════════════════════════════════════
    elif data == "panel_broadcast":
        ctx.user_data['state'] = ST_BROADCAST
        await q.message.edit_text(
            "📨 <b>Xabar yuborish</b>\n\n"
            "Barcha foydalanuvchilarga yuboriladigan xabarni kiriting.\n"
            "Matn, rasm, video — hammasi bo'ladi.\n\n"
            "❌ Bekor: /cancel",
            parse_mode="HTML"
        )

    # ═══════════════════════════════════════════
    # 🎬 KINO YUKLASH
    # ═══════════════════════════════════════════
    elif data == "panel_upload":
        ctx.user_data['state'] = ST_MOVIE_TITLE
        ctx.user_data['new_movie'] = {}
        await q.message.edit_text(
            "🎬 <b>Kino qo'shish — 1/6</b>\n\n"
            "Kino <b>nomini</b> kiriting:\n\n"
            "❌ Bekor: /cancel",
            parse_mode="HTML"
        )

    # ═══════════════════════════════════════════
    # 🤖 BOT HOLATI
    # ═══════════════════════════════════════════
    elif data == "panel_botstatus":
        await show_bot_status(q, ctx)

    # ═══════════════════════════════════════════
    # 👥 ADMINLAR
    # ═══════════════════════════════════════════
    elif data == "panel_admins":
        await show_admins_panel(q, uid)

    elif data == "admin_add":
        if not is_owner(uid):
            await q.answer("⛔ Faqat egasi admin qo'sha oladi!", show_alert=True)
            return
        ctx.user_data['state'] = ST_ADD_ADMIN
        await q.message.edit_text(
            "👤 <b>Admin qo'shish</b>\n\n"
            "Yangi adminning <b>Telegram ID</b> sini yuboring:\n\n"
            "❌ Bekor: /cancel",
            parse_mode="HTML"
        )

    elif data.startswith("admin_remove_"):
        if not is_owner(uid):
            await q.answer("⛔ Faqat egasi admin o'chira oladi!", show_alert=True)
            return
        target_id = int(data.split("_")[2])
        db.remove_admin(target_id)
        await show_admins_panel(q, uid)

    # Kino o'chirish
    elif data.startswith("del_movie_"):
        movie_id = int(data.split("_")[2])
        db.delete_movie(movie_id)
        await q.answer("✅ O'chirildi")
        await show_movies_list(q)


# ─── Panel ko'rsatuvchi funksiyalar ──────────────

async def show_channels_panel(q):
    channels = db.get_all_channels()
    text = "📡 <b>Kanallarni sozlash</b>\n\n"
    kb = []
    if channels:
        for ch in channels:
            status = "✅" if ch['active'] else "❌"
            kb.append([
                InlineKeyboardButton(f"{status} {ch['title']}", callback_data=f"ch_toggle_{ch['id']}"),
                InlineKeyboardButton("🗑", callback_data=f"ch_del_{ch['id']}")
            ])
        text += f"Jami: {len(channels)} ta kanal\n✅ = faol, ❌ = o'chiq"
    else:
        text += "Hozircha kanal yo'q."
    kb += [
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="ch_add")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="panel_main")]
    ]
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def show_stats_panel(q):
    total_users  = db.users_count()
    today_users  = db.users_today()
    total_movies = db.movies_count()
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🆕 Bugun qo'shildi: <b>{today_users}</b>\n"
        f"🎬 Jami kinolar: <b>{total_movies}</b>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kinolar ro'yxati", callback_data="stats_movies")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="panel_main")]
    ])
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def show_movies_list(q, page=0):
    movies = db.get_all_movies()
    per_page = 8
    total = len(movies)
    start = page * per_page
    page_movies = movies[start:start+per_page]

    text = f"🎬 <b>Kinolar ro'yxati</b> ({total} ta)\n\n"
    kb = []
    for m in page_movies:
        v = "✅" if m['file_id'] else "❌"
        text += f"{v} <b>{m['title']}</b> ({m['year']}) — 👁 {m['views']}\n"
        kb.append([
            InlineKeyboardButton(f"🗑 {m['title'][:20]}", callback_data=f"del_movie_{m['id']}")
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"stats_page_{page-1}"))
    if start + per_page < total:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"stats_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("◀️ Orqaga", callback_data="panel_stats")])
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def show_bot_status(q, ctx):
    total_users  = db.users_count()
    today_users  = db.users_today()
    total_movies = db.movies_count()
    active_chs   = len(db.get_active_channels())
    admins       = db.get_admins()

    text = (
        "🤖 <b>Bot holati</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"🆕 Bugun: <b>{today_users}</b>\n"
        f"🎬 Kinolar: <b>{total_movies}</b>\n"
        f"📡 Faol kanallar: <b>{active_chs}</b>\n"
        f"👮 Adminlar soni: <b>{len(admins)}</b>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="panel_main")]])
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def show_admins_panel(q, uid):
    admins = db.get_admins()
    text = "👥 <b>Adminlar</b>\n\n"
    kb = []
    for adm_id in admins:
        text += f"• <code>{adm_id}</code>\n"
        if is_owner(uid):
            kb.append([InlineKeyboardButton(
                f"❌ {adm_id} ni o'chirish",
                callback_data=f"admin_remove_{adm_id}"
            )])
    if not admins:
        text += "Hozircha qo'shimcha admin yo'q."

    bottom = []
    if is_owner(uid):
        bottom.append(InlineKeyboardButton("➕ Admin qo'shish", callback_data="admin_add"))
    bottom_row = [bottom] if bottom else []
    kb += bottom_row + [[InlineKeyboardButton("◀️ Orqaga", callback_data="panel_main")]]
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════
#  MATN ORQALI STATE HANDLER
# ════════════════════════════════════════════════

async def handle_text_states(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    text  = update.message.text.strip() if update.message.text else ""
    state = ctx.user_data.get('state')

    # ── Kanal qo'shish ──
    if state == ST_ADD_CHANNEL:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text(
                "❌ Format noto'g'ri!\n"
                "<code>kanal_id | Nomi | https://t.me/link</code>",
                parse_mode="HTML"
            )
            return
        db.add_channel(parts[0], parts[1], parts[2])
        ctx.user_data.pop('state', None)
        await update.message.reply_text(
            f"✅ <b>{parts[1]}</b> kanali qo'shildi!",
            parse_mode="HTML", reply_markup=main_menu_kb()
        )

    # ── Broadcast ──
    elif state == ST_BROADCAST:
        if not is_admin(uid): return
        ctx.user_data.pop('state', None)
        users = db.get_all_users()
        sent = failed = 0
        msg = await update.message.reply_text(f"📨 Yuborilmoqda... (0/{len(users)})")
        for i, u in enumerate(users):
            try:
                await ctx.bot.copy_message(
                    chat_id=u['id'],
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                sent += 1
            except TelegramError:
                failed += 1
            if (i+1) % 20 == 0:
                await msg.edit_text(f"📨 Yuborilmoqda... ({i+1}/{len(users)})")
            await asyncio.sleep(0.05)
        await msg.edit_text(
            f"✅ Xabar yuborildi!\n"
            f"✅ Muvaffaqiyatli: {sent}\n"
            f"❌ Yuborilmadi: {failed}"
        )

    # ── Admin qo'shish ──
    elif state == ST_ADD_ADMIN:
        if not is_owner(uid): return
        try:
            new_admin_id = int(text)
            db.add_admin(new_admin_id, uid)
            ctx.user_data.pop('state', None)
            await update.message.reply_text(
                f"✅ <code>{new_admin_id}</code> admin qilindi!",
                parse_mode="HTML", reply_markup=main_menu_kb()
            )
        except ValueError:
            await update.message.reply_text("❌ Faqat raqam kiriting!")

    # ── Kino qo'shish (bosqichma-bosqich) ──
    elif state == ST_MOVIE_TITLE:
        ctx.user_data['new_movie']['title'] = text
        ctx.user_data['state'] = ST_MOVIE_YEAR
        await update.message.reply_text("📅 <b>2/6</b> — Yilini kiriting (misol: 2023):", parse_mode="HTML")

    elif state == ST_MOVIE_YEAR:
        ctx.user_data['new_movie']['year'] = text
        ctx.user_data['state'] = ST_MOVIE_GENRE
        await update.message.reply_text("🎭 <b>3/6</b> — Janrini kiriting (misol: Triller, Komediya):", parse_mode="HTML")

    elif state == ST_MOVIE_GENRE:
        ctx.user_data['new_movie']['genre'] = text
        ctx.user_data['state'] = ST_MOVIE_RATING
        await update.message.reply_text("⭐ <b>4/6</b> — Reytingini kiriting (misol: 8.5):", parse_mode="HTML")

    elif state == ST_MOVIE_RATING:
        ctx.user_data['new_movie']['rating'] = text
        ctx.user_data['state'] = ST_MOVIE_DESC
        await update.message.reply_text(
            "📝 <b>5/6</b> — Tavsifini kiriting.\n(O'tkazib yuborish uchun — kiriting):",
            parse_mode="HTML"
        )

    elif state == ST_MOVIE_DESC:
        ctx.user_data['new_movie']['desc'] = text
        ctx.user_data['state'] = ST_MOVIE_VIDEO
        m = ctx.user_data['new_movie']
        movie_id = db.add_movie(
            m['title'], m['year'], m['genre'], m['rating'], m.get('desc','')
        )
        ctx.user_data['pending_movie_id'] = movie_id
        await update.message.reply_text(
            f"📹 <b>6/6</b> — Kino ma'lumotlari saqlandi!\n\n"
            f"🎬 <b>{m['title']}</b> ({m['year']})\n\n"
            "Endi <b>video faylni</b> yuboring:",
            parse_mode="HTML"
        )

    else:
        # Oddiy qidiruv
        await search_movie(update, ctx)


async def handle_video_upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    movie_id = ctx.user_data.get('pending_movie_id')
    if not movie_id:
        await update.message.reply_text("⚠️ Avval /admin → Kino yuklash orqali kino ma'lumotlarini kiriting.")
        return

    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ Faqat video fayl yuboring!")
        return

    db.update_movie_file(movie_id, video.file_id)
    ctx.user_data.pop('pending_movie_id', None)
    ctx.user_data.pop('state', None)
    movie = db.get_movie_by_id(movie_id)

    await update.message.reply_text(
        f"🎉 <b>{movie['title']}</b> to'liq qo'shildi!\n"
        f"🆔 ID: {movie_id}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.")
    if is_admin(update.effective_user.id):
        await update.message.reply_text("⚙️ Admin panel:", reply_markup=main_menu_kb())
# ════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════

def main():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("admin",  admin_panel))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CallbackQueryHandler(check_sub_callback,  pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(movie_callback,      pattern=r"^movie_\d+$"))
    app.add_handler(CallbackQueryHandler(panel_callback,      pattern="^(panel_|ch_|stats_|admin_|del_movie_)"))

    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_states))

    logger.info("🚀 Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
