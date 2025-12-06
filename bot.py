import os
import sqlite3
import dns.resolver
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ==========================
# DATABASE CHI TIÊU
# ==========================
conn = sqlite3.connect("expenses.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        amount INTEGER,
        note TEXT,
        date TEXT
    )
""")
conn.commit()

def parse_money(text):
    text = text.lower().replace(" ", "")
    if text.endswith("k"):
        return int(float(text[:-1]) * 1000)
    if text.endswith("m"):
        return int(float(text[:-1]) * 1_000_000)
    return int(text)

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("Lệnh này chỉ dùng trong nhóm!")

    try:
        amount = parse_money(context.args[0])
        note = " ".join(context.args[1:])
        user = update.effective_user.first_name
        date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("INSERT INTO expenses (user, amount, note, date) VALUES (?, ?, ?, ?)",
                       (user, amount, note, date))
        conn.commit()

        await update.message.reply_text(f"💰 {user} vừa ghi: {amount:,} vnđ – {note}")

    except Exception:
        await update.message.reply_text("Sai cú pháp!\nVD: /add 50k cafe")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("Lệnh này chỉ dùng trong nhóm!")

    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT user, amount FROM expenses WHERE date=?", (today,))
    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("Hôm nay chưa có chi tiêu nào!")

    summary = {}
    for user, amount in rows:
        summary[user] = summary.get(user, 0) + amount

    text = "📅 *Chi tiêu hôm nay:*\n"
    for user, total in summary.items():
        text += f"- {user}: {total:,} vnđ\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("Lệnh này chỉ dùng trong nhóm!")

    month_now = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT user, amount FROM expenses WHERE date LIKE ?", (month_now + "%",))
    rows = cursor.fetchall()

    if not rows:
        return await update.message.reply_text("Chưa có chi tiêu nào trong tháng!")

    summary = {}
    for user, amount in rows:
        summary[user] = summary.get(user, 0) + amount

    text = "📆 *Chi tiêu tháng này:*\n"
    for user, total in summary.items():
        text += f"- {user}: {total:,} vnđ\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ==========================
# DNS CHECKER – PRIVATE CHAT
# ==========================
async def dns_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return  # Không xử lý trong nhóm

    domains = update.message.text.split()
    reply_msg = ""

    for domain in domains:
        reply_msg += f"🔍 *{domain}*\n"
        try:
            answers = dns.resolver.resolve(domain, "A")
            reply_msg += "A Records:\n"
            for r in answers:
                reply_msg += f"- {r}\n"
        except:
            reply_msg += "❌ Không tìm thấy A record\n"

        try:
            answers = dns.resolver.resolve(domain, "CNAME")
            reply_msg += "CNAME:\n"
            for r in answers:
                reply_msg += f"- {r}\n"
        except:
            reply_msg += "❌ Không có CNAME\n"

        reply_msg += "\n"

    await update.message.reply_text(reply_msg, parse_mode="Markdown")


# ==========================
# MAIN APP
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot hoạt động!\n"
        "- Nhắn riêng để kiểm tra DNS.\n"
        "- Vào nhóm để ghi chi tiêu.\n"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # GROUP FEATURES
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("month", month))

    # PRIVATE CHAT DNS
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), dns_check))

    # START
    app.add_handler(CommandHandler("start", start))

    app.run_polling()


if __name__ == "__main__":
    main()
