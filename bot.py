# -*- coding: utf-8 -*-
import dns.resolver
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    Filters,
    CallbackContext
)

TOKEN = "YOUR_TOKEN_HERE"

# ===========================
#   STATES
# ===========================
CNAME_INPUT = 1
NS_INPUT = 2
ADD_EXPENSE = 3

expenses = {}  # Lưu chi tiêu trong RAM

# ===========================
#   MENU START
# ===========================
def start(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("🔷 Kiểm tra CNAME", callback_data="check_cname"),
            InlineKeyboardButton("🔷 Kiểm tra DNS (NS)", callback_data="check_ns"),
        ],
        [
            InlineKeyboardButton("💰 Ghi chi tiêu", callback_data="add_expense"),
            InlineKeyboardButton("📊 Xem chi tiêu", callback_data="view_expense")
        ]
    ]
    update.message.reply_text(
        "Chọn chức năng 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ===========================
#   CALLBACK MENU
# ===========================
def menu_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "check_cname":
        query.edit_message_text("Nhập domain cần kiểm tra CNAME:")
        return CNAME_INPUT

    if query.data == "check_ns":
        query.edit_message_text("Nhập domain cần kiểm tra NS:")
        return NS_INPUT

    if query.data == "add_expense":
        query.edit_message_text("Nhập chi tiêu theo dạng:\n\nTên người - số tiền - ghi chú")
        return ADD_EXPENSE

    if query.data == "view_expense":
        if not expenses:
            query.edit_message_text("📭 Chưa có chi tiêu nào.")
        else:
            text = "📊 *Danh sách chi tiêu:*\n\n"
            for user, money in expenses.items():
                text += f"• *{user}*: `{money:,}`đ\n"
            query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END


# ===========================
#   CHECK CNAME
# ===========================
def check_cname(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        res = dns.resolver.resolve(domain, "CNAME")
        result = "\n".join(str(r.target) for r in res)
        update.message.reply_text(f"🔍 *CNAME:* \n`{result}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text(f"❌ Không tìm thấy CNAME:\n{e}")
    return ConversationHandler.END


# ===========================
#   CHECK NS
# ===========================
def check_ns(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        res = dns.resolver.resolve(domain, "NS")
        result = "\n".join(str(r.target) for r in res)
        update.message.reply_text(f"🔍 *DNS NS:* \n`{result}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text(f"❌ Lỗi:\n{e}")
    return ConversationHandler.END


# ===========================
#   ADD EXPENSE
# ===========================
def save_expense(update: Update, context: CallbackContext):
    text = update.message.text.strip()

    try:
        name, money, note = text.split("-", 2)
        name = name.strip()
        money = int(money.strip())

        expenses[name] = expenses.get(name, 0) + money
        update.message.reply_text(f"✅ Đã ghi: *{name}* - `{money:,}`đ", parse_mode=ParseMode.MARKDOWN)
    except:
        update.message.reply_text("❌ Sai định dạng!\nVí dụ: `Huy - 50000 - ăn sáng`")

    return ConversationHandler.END


# ===========================
#   MAIN
# ===========================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_handler)],
        states={
            CNAME_INPUT: [MessageHandler(Filters.text & ~Filters.command, check_cname)],
            NS_INPUT: [MessageHandler(Filters.text & ~Filters.command, check_ns)],
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, save_expense)],
        },
        fallbacks=[]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv)

    print("BOT ĐANG CHẠY…")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
