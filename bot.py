import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
import dns.resolver
import requests
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================
#   HANDLERS DNS / CNAME
# ======================

CHOOSING, CHECK_CNAME, CHECK_DNS = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔹 Kiểm tra CNAME", callback_data="cname")],
        [InlineKeyboardButton("🔹 Kiểm tra DNS (NS)", callback_data="dns")],
    ]
    await update.message.reply_text("Chọn loại kiểm tra 👇", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING


async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cname":
        await query.edit_message_text("Nhập domain muốn kiểm tra CNAME:")
        return CHECK_CNAME

    if query.data == "dns":
        await query.edit_message_text("Nhập domain muốn kiểm tra DNS:")
        return CHECK_DNS


async def check_cname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()

    try:
        answers = dns.resolver.resolve(domain, "CNAME")
        cname = "\n".join([str(r.target) for r in answers])
        await update.message.reply_text(f"🔍 Kết quả CNAME của {domain}:\n\n{cname}")
    except Exception as e:
        await update.message.reply_text(f"⚠ Lỗi: {e}")

    return ConversationHandler.END


async def check_dns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    domain = update.message.text.strip()

    try:
        answers = dns.resolver.resolve(domain, "NS")
        ns_records = "\n".join([str(r.target) for r in answers])
        await update.message.reply_text(f"🔍 Kết quả DNS NS của {domain}:\n\n{ns_records}")
    except Exception as e:
        await update.message.reply_text(f"⚠ Lỗi: {e}")

    return ConversationHandler.END

# ======================
#  CHI TIÊU — CHECK CHAT ID GROUP
# ======================

GROUP_ID = -1000000000000  # sửa thành group thật  

async def add_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != GROUP_ID:
        return  

    try:
        text = update.message.text
        money = int(text.split()[0])
        desc = " ".join(text.split()[1:])
        await update.message.reply_text(f"Đã ghi {money}đ — {desc}")
    except:
        await update.message.reply_text("Sai định dạng. Ví dụ: `50000 ăn sáng`")

# ======================
#  KHỞI TẠO APP
# ======================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(menu_button)],
            CHECK_CNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_cname)],
            CHECK_DNS: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_dns)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_cost))

    print("Bot đang chạy…")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
