# -*- coding: utf-8 -*-
import requests
import dns.resolver
import traceback
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
)

TOKEN = "YOUR_TOKEN_HERE"

# -----------------------------
# MENU CHÍNH
# -----------------------------
def start(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("🔷 Kiểm tra CNAME", callback_data="check_cname"),
            InlineKeyboardButton("🔷 Kiểm tra DNS (NS)", callback_data="check_ns"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Chọn loại kiểm tra 👇", reply_markup=reply_markup)


# -----------------------------
# CALLBACK BUTTONS
# -----------------------------
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "check_cname":
        query.message.reply_text("Nhập domain cần kiểm tra CNAME:")
        return 1

    if query.data == "check_ns":
        query.message.reply_text("Nhập domain cần kiểm tra NS:")
        return 2


# -----------------------------
# CHECK CNAME
# -----------------------------
def handle_cname(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        answer = dns.resolver.resolve(domain, "CNAME")
        result = "\n".join([str(rdata.target) for rdata in answer])
        update.message.reply_text(f"🔍 *CNAME Record:* \n`{result}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text("❌ Không tìm thấy CNAME.\n" + str(e))
    return ConversationHandler.END


# -----------------------------
# CHECK NS
# -----------------------------
def handle_ns(update: Update, context: CallbackContext):
    domain = update.message.text.strip()
    try:
        answer = dns.resolver.resolve(domain, "NS")
        result = "\n".join([str(rdata.target) for rdata in answer])
        update.message.reply_text(f"🔍 *NS Record:* \n`{result}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        update.message.reply_text("❌ Không tìm thấy NS.\n" + str(e))
    return ConversationHandler.END


# -----------------------------
# MAIN
# -----------------------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            1: [MessageHandler(Filters.text & ~Filters.command, handle_cname)],
            2: [MessageHandler(Filters.text & ~Filters.command, handle_ns)],
        },
        fallbacks=[]
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv)

    print("Bot đang chạy...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
