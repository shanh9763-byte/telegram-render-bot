import os
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -----------------------------
#  COMMAND: /start
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot online rồi bro 😎\nGửi tên miền để kiểm tra!")

# -----------------------------
#  FUNCTION CHECK DNS
# -----------------------------
def check_domain(domain: str):
    try:
        res = requests.get(f"https://api.domainsdb.info/v1/domains/search?domain={domain}&zone=com")
        return res.status_code == 200
    except:
        return False

# -----------------------------
#  HANDLE NORMAL TEXT
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    domain = update.message.text.strip()

    await update.message.reply_text(f"⏳ Đang kiểm tra `{domain}`…", parse_mode="Markdown")

    ok = check_domain(domain)

    if ok:
        await update.message.reply_text(f"✅ Domain `{domain}` hợp lệ!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Domain `{domain}` sai hoặc không tồn tại.", parse_mode="Markdown")

# -----------------------------
#  MAIN APP
# -----------------------------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("BOT is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
