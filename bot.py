import os
import json
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext
)
import dns.resolver

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CHOOSING, CNAME_INPUT, DNS_INPUT = range(3)

def group_file(chat_id):
    return f"{DATA_DIR}/group_{chat_id}.json"

def load_expenses(chat_id):
    f = group_file(chat_id)
    if not os.path.exists(f):
        return []
    return json.load(open(f, "r", encoding="utf-8"))

def save_expenses(chat_id, data):
    f = group_file(chat_id)
    json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# /start
def start(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type in ("group", "supergroup"):
        update.message.reply_text(
            "👋 Bot chi tiêu nhóm\n\n"
            "• /add 200k ăn sáng\n"
            "• /total\n"
            "• /total month\n"
            "• /export\n\n"
            "👉 Nhắn riêng tao để dùng DNS."
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🔹 Kiểm tra CNAME", callback_data="cname")],
        [InlineKeyboardButton("🔹 Kiểm tra DNS (NS)", callback_data="dns")],
    ]
    update.message.reply_text("Chọn chức năng 👇", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING

def menu(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()

    if q.data == "cname":
        q.edit_message_text("Nhập domain để kiểm tra CNAME:")
        return CNAME_INPUT

    if q.data == "dns":
        q.edit_message_text("Nhập domain để kiểm tra DNS:")
        return DNS_INPUT

def cname_lookup(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        answers = dns.resolver.resolve(domain, "CNAME")
        text = "\n".join(str(r.target) for r in answers)
        update.message.reply_text(f"CNAME của {domain}:\n{text}")
    except Exception as e:
        update.message.reply_text(str(e))
    return ConversationHandler.END

def dns_lookup(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        answers = dns.resolver.resolve(domain, "NS")
        text = "\n".join(str(r.target) for r in answers)
        update.message.reply_text(f"DNS NS của {domain}:\n{text}")
    except Exception as e:
        update.message.reply_text(str(e))
    return ConversationHandler.END

# Chi tiêu
def add_exp(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return

    if len(context.args) < 2:
        update.message.reply_text("Ví dụ: /add 200k ăn sáng")
        return

    raw = context.args[0].lower().replace("k", "000")
    try:
        amount = int(raw)
    except:
        update.message.reply_text("Số tiền không hợp lệ.")
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
    update.message.reply_text(f"Đã ghi {amount}đ – {note}")

def total(update: Update, context: CallbackContext):
    chat = update.effective_chat
    data = load_expenses(chat.id)

    mode = "today"
    if context.args and context.args[0] == "month":
        mode = "month"

    now = datetime.now()
    s = 0
    for e in data:
        t = datetime.fromisoformat(e["time"])
        if mode == "today" and t.date() == now.date():
            s += e["amount"]
        elif mode == "month" and t.month == now.month and t.year == now.year:
            s += e["amount"]

    update.message.reply_text(f"Tổng chi {mode}: {s}đ")

def export_data(update: Update, context: CallbackContext):
    chat = update.effective_chat
    f = group_file(chat.id)
    if not os.path.exists(f):
        update.message.reply_text("Chưa có dữ liệu.")
        return
    update.message.reply_document(open(f, "rb"), filename=os.path.basename(f))

# MAIN
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(menu)],
            CNAME_INPUT: [MessageHandler(Filters.text & ~Filters.command, cname_lookup)],
            DNS_INPUT: [MessageHandler(Filters.text & ~Filters.command, dns_lookup)],
        },
        fallbacks=[]
    )
    dp.add_handler(conv)

    dp.add_handler(CommandHandler("add", add_exp))
    dp.add_handler(CommandHandler("total", total))
    dp.add_handler(CommandHandler("export", export_data))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
