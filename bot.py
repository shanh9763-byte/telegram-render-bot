import os
import csv
import asyncio
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

import dns.resolver


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ----------------------------------------
# STATES FOR INLINE MENU (PRIVATE CHAT)
# ----------------------------------------
ASK_DOMAIN_CNAME, ASK_DOMAIN_DNS = range(2)


# =========================
# GROUP FUNCTIONS (EXPENSE)
# =========================
expenses = {}  # { chat_id : [ {amount, desc, timestamp}, ... ] }


def add_expense(chat_id, amount, desc):
    if chat_id not in expenses:
        expenses[chat_id] = []
    expenses[chat_id].append({
        "amount": amount,
        "desc": desc,
        "time": datetime.now()
    })


def get_today_total(chat_id):
    if chat_id not in expenses:
        return 0

    today = datetime.now().date()
    return sum(e["amount"] for e in expenses[chat_id] if e["time"].date() == today)


def get_month_total(chat_id):
    if chat_id not in expenses:
        return 0

    now = datetime.now()
    return sum(
        e["amount"] for e in expenses[chat_id]
        if e["time"].year == now.year and e["time"].month == now.month
    )


def export_csv(chat_id):
    filename = f"expenses_{chat_id}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Amount", "Description", "Time"])
        for e in expenses.get(chat_id, []):
            writer.writerow([e["amount"], e["desc"], e["time"]])
    return filename


# =========================
# PRIVATE MENU / START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    # -------- GROUP START --------
    if chat.type in ("group", "supergroup"):
        txt = (
            "👋 *Xin chào mọi người!*\n\n"
            "💸 *Hệ thống quản lý chi tiêu nhóm*\n"
            "• /add 200k ăn sáng\n"
            "• /total – Tổng hôm nay\n"
            "• /total month – Tổng tháng\n"
            "• /export – Xuất file CSV\n\n"
            "💬 Dùng chức năng DNS trong chat riêng."
        )
        await update.message.reply_markdown(txt)
        return

    # -------- PRIVATE START --------
    keyboard = [
        [
            InlineKeyboardButton("🔷 Kiểm tra CNAME", callback_data="check_cname"),
            InlineKeyboardButton("🔷 Kiểm tra DNS (NS)", callback_data="check_dns"),
        ]
    ]
    await update.message.reply_text(
        "Chọn loại kiểm tra 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# DNS LOOKUP
# =========================

async def cname_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = context.args[0]
    try:
        answers = dns.resolver.resolve(domain, "CNAME")
        cname = "\n".join(str(r) for r in answers)
        await update.message.reply_text(f"🔎 *CNAME Record:*\n{cname}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")


async def dns_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = context.args[0]
    try:
        answers = dns.resolver.resolve(domain, "NS")
        ns_list = "\n".join(str(r) for r in answers)
        await update.message.reply_text(f"🔎 *DNS NS Record:*\n{ns_list}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")


# =========================
# CALLBACK BUTTON → ASK DOMAIN
# =========================

async def cb_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_cname":
        await query.edit_message_text("Nhập domain để kiểm tra CNAME:")
        return ASK_DOMAIN_CNAME

    if query.data == "check_dns":
        await query.edit_message_text("Nhập domain để kiểm tra DNS (NS):")
        return ASK_DOMAIN_DNS


# =========================
# DOMAIN PROCESS (USER INPUT)
# =========================

async def process_cname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()
    context.args = [domain]
    await cname_lookup(update, context)
    return ConversationHandler.END


async def process_dns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()
    context.args = [domain]
    await dns_lookup(update, context)
    return ConversationHandler.END


# =========================
# GROUP COMMANDS
# =========================

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if len(context.args) < 2:
        await update.message.reply_text("❌ Sai cú pháp. Ví dụ: /add 200k ăn sáng")
        return

    amount_raw = context.args[0].lower().replace("k", "000")
    try:
        amount = int(amount_raw)
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    desc = " ".join(context.args[1:])
    add_expense(chat_id, amount, desc)

    await update.message.reply_text(f"✔ Đã thêm *{amount}đ* – {desc}", parse_mode="Markdown")


async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if context.args and context.args[0] == "month":
        t = get_month_total(chat_id)
        await update.message.reply_text(f"📆 Tổng tháng: *{t}đ*", parse_mode="Markdown")
        return

    t = get_today_total(chat_id)
    await update.message.reply_text(f"📅 Tổng hôm nay: *{t}đ*", parse_mode="Markdown")


async def export_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    file = export_csv(chat_id)
    await update.message.reply_document(open(file, "rb"))


# =========================
# MAIN APP
# =========================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation Handler (Private Menu)
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_select)],
        states={
            ASK_DOMAIN_CNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_cname)],
            ASK_DOMAIN_DNS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_dns)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("export", export_file))

    print("Bot đang chạy...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
