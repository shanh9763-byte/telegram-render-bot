import os
import json
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
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

CHOOSING, ASK_CNAME, ASK_DNS = range(3)

def group_file(chat_id):
    return f"{DATA_DIR}/group_{chat_id}.json"

def load_data(chat_id):
    f = group_file(chat_id)
    if not os.path.exists(f):
        return []
    return json.load(open(f, "r", encoding="utf-8"))

def save_data(chat_id, data):
    f = group_file(chat_id)
    json.dump(data, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# =====================
# /start
# =====================
def start(update: Update, context: CallbackContext):
    chat = update.effective_chat

    # GROUP MODE
    if chat.type in ("group", "supergroup"):
        update.message.reply_text(
            "👋 Bot chi tiêu nhóm đã hoạt động.\n\n"
            "Các lệnh:\n"
            "• /add 200k ăn sáng\n"
            "• /total – tổng hôm nay\n"
            "• /total month – tổng tháng\n"
            "• /export – tải dữ liệu JSON\n\n"
            "👉 Nhắn riêng để dùng tính năng DNS/CNAME."
        )
        return ConversationHandler.END

    # PRIVATE MODE
    keyboard = [
        [InlineKeyboardButton("🔹 Kiểm tra CNAME", callback_data="cname")],
        [InlineKeyboardButton("🔹 Kiểm tra DNS (NS)", callback_data="dns")],
    ]
    update.message.reply_text(
        "Chọn chức năng 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING

# =====================
# Inline buttons
# =====================
def menu(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()

    if q.data == "cname":
        q.edit_message_text("Nhập domain muốn kiểm tra CNAME:")
        return ASK_CNAME

    if q.data == "dns":
        q.edit_message_text("Nhập domain muốn kiểm tra DNS NS:")
        return ASK_DNS

# =====================
# DNS FUNCTIONS
# =====================
def cname_lookup(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        ans = dns.resolver.resolve(domain, "CNAME")
        result = "\n".join(str(r.target) for r in ans)
        update.message.reply_text(f"🔍 *CNAME của {domain}:*\n{result}", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"Lỗi: {e}")
    return ConversationHandler.END

def dns_lookup(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        ans = dns.resolver.resolve(domain, "NS")
        result = "\n".join(str(r.target) for r in ans)
        update.message.reply_text(f"🔍 *DNS NS của {domain}:*\n{result}", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"Lỗi: {e}")
    return ConversationHandler.END

# =====================
# ADD EXPENSE
# =====================
def add_exp(update: Update, context: CallbackContext):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return

    if len(context.args) < 2:
        update.message.reply_text("Sai cú pháp.\nVí dụ: /add 200k ăn sáng")
        return

    raw = context.args[0].lower().replace("k", "000")
    try:
        amount = int(raw)
    except:
        update.message.reply_text("❌ Số tiền không hợp lệ.")
        return

    note = " ".join(context.args[1:])
    user = update.effective_user.full_name

    data = load_data(chat.id)
    data.append({
        "user": user,
        "amount": amount,
        "note": note,
        "time": datetime.now().isoformat()
    })
    save_data(chat.id, data)

    update.message.reply_text(f"✔ Đã ghi {amount}đ – {note}")

# =====================
# TOTAL
# =====================
def total(update: Update, context: CallbackContext):
    chat = update.effective_chat

    data = load_data(chat.id)
    now = datetime.now()

    mode = "today"
    if context.args and context.args[0] == "month":
        mode = "month"

    s = 0
    for e in data:
        t = datetime.fromisoformat(e["time"])
        if mode == "today" and t.date() == now.date():
            s += e["amount"]
        elif mode == "month" and t.month == now.month and t.year == now.year:
            s += e["amount"]

    label = "hôm nay" if mode == "today" else "tháng này"
    update.message.reply_text(f"💵 Tổng chi {label}: {s}đ")

# =====================
# EXPORT JSON
# =====================
def export_file(update: Update, context: CallbackContext):
    chat = update.effective_chat
    f = group_file(chat.id)

    if not os.path.exists(f):
        update.message.reply_text("Chưa có dữ liệu.")
        return

    update.message.reply_document(open(f, "rb"), filename=os.path.basename(f))

# =====================
# MAIN
# =====================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # DNS conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(menu)],
            ASK_CNAME: [MessageHandler(Filters.text & ~Filters.command, cname_lookup)],
            ASK_DNS: [MessageHandler(Filters.text & ~Filters.command, dns_lookup)],
        },
        fallbacks=[],
    )
    dp.add_handler(conv)

    dp.add_handler(CommandHandler("add", add_exp))
    dp.add_handler(CommandHandler("total", total))
    dp.add_handler(CommandHandler("export", export_file))

    print("Bot đang chạy...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
