import asyncio
import logging
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from PIL import Image
import requests
from io import BytesIO
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---- LỆNH /start ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot đã hoạt động OK trên Render 🚀")

# ---- CHECK DNS ----
async def dns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        return await update.message.reply_text("Dùng: /dns domain.com")

    domain = context.args[0]
    await update.message.reply_text(f"Đang kiểm tra DNS cho {domain}...")

    try:
        r = requests.get(f"https://dns.google/resolve?name={domain}")
        data = r.json()
        await update.message.reply_text(str(data))
    except:
        await update.message.reply_text("Lỗi khi kiểm tra DNS.")

# ---- XỬ LÝ ẢNH ----
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    img_bytes = await file.download_as_bytearray()

    img = Image.open(BytesIO(img_bytes))
    img = img.convert("RGB")

    output = BytesIO()
    img.save(output, format="JPEG")
    output.seek(0)

    await update.message.reply_photo(photo=output, caption="Ảnh đã xử lý xong!")

# ---- HÀM MAIN ----
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dns", dns))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # 🚀 Không dùng Updater – chỉ dùng run_polling()
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
