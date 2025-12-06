import os
import json
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import dns.resolver

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ================================
# Conversation states
# ================================
CHOOSING, CNAME_INPUT, DNS_INPUT = range(3)


# ================================
# Helper — JSON per group
# ================================
def get_group_file(chat_id):
    return os.path.join(DATA_DIR, f"group_{chat_id}.json")


def load_expenses(chat_id):
    file = get_group_file(chat_id)
    if not os.path.exists(file):
        return []
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_expenses(chat_id, data):
    file = get_group_file(chat_id)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ================================
# /start
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type in ("group", "supergroup"):
        await update.message.reply_text(
            "👋 *Bot chi tiêu nhóm*\n\n"
            "Các lệnh:\n"
            "• /add 200k ăn sáng\n"
            "• /total – tổng hôm nay\n"
            "• /total month – tổng tháng\n"
            "• /export – xuất file\n\n"
            "👉 Nhắn riêng để dùng tính năng DNS.",
            parse_mode="Markdown"
        )
        return

    # PRIVATE
    keyboard = [
        [
            InlineKeyboardButton("🔹 Kiểm tra CNAME", callback_data="cname"),
        ],
        [
            InlineKeyboardButton("🔹 Kiểm tra DNS (NS)", callback_data="dns"),
        ],
    ]
    await update.message.reply_text(
        "Chọn chức năng 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING


# ================================
# Callback buttons
# ================================
async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cname":
        await q.edit_message_text("Nhập domain để kiểm tra CNAME:")
        return CNAME_INPUT

    if q.data == "dns":
        await q.edit_message_text("Nhập domain để kiểm tra DNS (NS):")
        return DNS_INPUT


# ================================
# DNS / CNAME
# ================================
async def check_cname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()

    try:
        answers = dns.resolver.resolve(domain, "CNAME")
        text = "\n".join(str(r.target) for r in answers)
        await update.message.reply_text(f"🔎 *CNAME của {domain}:*\n{text}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

    return ConversationHandler.END


async def check_dns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()

    try:
        answers = dns.resolver.resolve(domain, "NS")
        text = "\n".join(str(r.target) for r in answers)
        await update.message.reply_text(f"🔎 *DNS NS của {domain}:*\n{text}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

    return ConversationHandler.END


# ================================
# Chi tiêu nhóm
# ================================
async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):
        return

    if len(context.args) < 2:
        await update.message.reply_text("Sai cú pháp. Ví dụ:\n/add 200k ăn sáng")
        return

    amount_raw = context.args[0].lower().replace("k", "000")
    try:
        amount = int(amount_raw)
    except:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    note = " ".join(context.args[1:])
    user = update.effective_user.full_name

    data = load_expenses(chat.id)
    data.append({
        "user": user,
        "amount": amount,
        "note": note,
        "time": datetime.now().isoformat()
    })
    save_expenses(chat.id, data)

    await update.message.reply_text(f"✔ Đã ghi {amount}đ – {note}")


async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return

    mode = "today"
    if context.args:
        if context.args[0] == "month":
            mode = "month"

    data = load_expenses(chat.id)

    now = datetime.now()
    total = 0
    for e in data:
        t = datetime.fromisoformat(e["time"])
        if mode == "today" and t.date() == now.date():
            total += e["amount"]
        elif mode == "month" and t.year == now.year and t.month == now.month:
            total += e["amount"]

    label = "hôm nay" if mode == "today" else "tháng này"
    await update.message.reply_text(f"💰 Tổng chi {label}: {total}đ")


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return

    file = get_group_file(chat.id)
    if not os.path.exists(file):
        await update.message.reply_text("Chưa có dữ liệu.")
        return

    await update.message.reply_document(file, caption="📄 File chi tiêu JSON")


# ================================
# MAIN APP
# ================================
def main():

    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation for DNS
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(menu_choice)],
            CNAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_cname)],
            DNS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_dns)],
        },
        fallbacks=[],
        per_message=True
    )
    app.add_handler(conv)

    # Group expense commands
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("export", export_data))

    print("🔥 Bot đang chạy...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
