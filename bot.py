import logging
import os
import re
import sqlite3
from datetime import datetime, date

import dns.resolver
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------- LOGGING -----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH = "expenses.db"

# ================== DB CHI TIÊU ==================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            amount REAL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def add_expense_db(chat_id: int, user_id: int, username: str, amount: float, note: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO expenses (chat_id, user_id, username, amount, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chat_id, user_id, username, amount, note),
    )
    conn.commit()
    conn.close()


def get_today_stats(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT username, SUM(amount)
        FROM expenses
        WHERE chat_id = ?
          AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
        GROUP BY username
        """,
        (chat_id,),
    )
    rows = cur.fetchall()

    cur.execute(
        """
        SELECT SUM(amount)
        FROM expenses
        WHERE chat_id = ?
          AND DATE(created_at, 'localtime') = DATE('now', 'localtime')
        """,
        (chat_id,),
    )
    total = cur.fetchone()[0] or 0
    conn.close()
    return rows, total


def get_month_stats(chat_id: int):
    today = date.today()
    ym = today.strftime("%Y-%m")  # "2025-12" dạng như vậy

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT username, SUM(amount)
        FROM expenses
        WHERE chat_id = ?
          AND strftime('%Y-%m', datetime(created_at, 'localtime')) = ?
        GROUP BY username
        """,
        (chat_id, ym),
    )
    rows = cur.fetchall()

    cur.execute(
        """
        SELECT SUM(amount)
        FROM expenses
        WHERE chat_id = ?
          AND strftime('%Y-%m', datetime(created_at, 'localtime')) = ?
        """,
        (chat_id, ym),
    )
    total = cur.fetchone()[0] or 0
    conn.close()
    return rows, total

# ================== PARSE SỐ TIỀN ==================

def parse_amount(token: str) -> float:
    """
    Hỗ trợ:
    - 50000
    - 50k / 50K -> 50000
    - 1m / 1.5m -> 1_000_000 / 1_500_000
    """
    token = token.lower().strip()
    mul = 1.0

    if token.endswith("k"):
        mul = 1000.0
        token = token[:-1]
    elif token.endswith("m"):
        mul = 1_000_000.0
        token = token[:-1]

    token = token.replace(",", ".")
    value = float(token)
    return value * mul

# ================== HANDLER CHI TIÊU (GROUP) ==================

HELP_TEXT_GROUP = (
    "👛 *Bot quản lý chi tiêu gia đình*\n\n"
    "Trong *nhóm* này, bot dùng để ghi lại chi tiêu:\n\n"
    "• /add `<số tiền>` `<ghi chú>`\n"
    "  Ví dụ: `/add 50k ăn sáng`\n"
    "         `/add 120000 mua tã cho con`\n\n"
    "• /today – Xem tổng chi hôm nay (chi tiết từng người)\n"
    "• /month – Xem tổng chi tháng này\n\n"
    "_Nhắn riêng bot sẽ dùng để kiểm tra DNS/CNAME._"
)

HELP_TEXT_PRIVATE = (
    "🛰 *Bot kiểm tra DNS / CNAME*\n\n"
    "Trong chat *riêng* này, bạn chỉ cần gửi tên miền:\n\n"
    "`google.com`\n"
    "`abc.xyz`\n"
    "`sub.domain.com`\n\n"
    "Bot sẽ trả lại bản ghi A và CNAME (nếu có).\n\n"
    "_Trong nhóm, bot dùng để quản lý chi tiêu vợ chồng._"
)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ("group", "supergroup"):
        await update.message.reply_markdown(HELP_TEXT_GROUP)
    else:
        await update.message.reply_markdown(HELP_TEXT_PRIVATE)


async def add_expense_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chỉ dùng trong group: /add 50k ăn sáng"""
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm (group).")
        return

    if not context.args:
        await update.message.reply_text("Dùng: /add <số tiền> <ghi chú>\nVD: /add 50k ăn sáng")
        return

    try:
        amount = parse_amount(context.args[0])
    except Exception:
        await update.message.reply_text("Không hiểu số tiền. Ví dụ: 50k, 120000, 1.5m")
        return

    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    user = update.effective_user

    add_expense_db(
        chat_id=chat.id,
        user_id=user.id,
        username=user.full_name or (user.username or "unknown"),
        amount=amount,
        note=note,
    )

    pretty_amount = f"{amount:,.0f}".replace(",", ".")
    await update.message.reply_text(f"✅ Đã ghi: {pretty_amount}đ – {note}")


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm (group).")
        return

    rows, total = get_today_stats(chat.id)
    if not rows:
        await update.message.reply_text("Hôm nay chưa có chi tiêu nào.")
        return

    lines = ["📅 *Chi tiêu hôm nay:*"]
    for username, amount in rows:
        pretty = f"{amount:,.0f}".replace(",", ".")
        lines.append(f"• {username}: {pretty}đ")

    pretty_total = f"{total:,.0f}".replace(",", ".")
    lines.append(f"\n💰 *Tổng:* {pretty_total}đ")

    await update.message.reply_markdown("\n".join(lines))


async def month_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh này chỉ dùng trong nhóm (group).")
        return

    rows, total = get_month_stats(chat.id)
    if not rows:
        await update.message.reply_text("Tháng này chưa có chi tiêu nào.")
        return

    ym = date.today().strftime("%m/%Y")
    lines = [f"📆 *Chi tiêu tháng {ym}:*"]
    for username, amount in rows:
        pretty = f"{amount:,.0f}".replace(",", ".")
        lines.append(f"• {username}: {pretty}đ")

    pretty_total = f"{total:,.0f}".replace(",", ".")
    lines.append(f"\n💰 *Tổng:* {pretty_total}đ")

    await update.message.reply_markdown("\n".join(lines))


# ================== DNS CHECK (PRIVATE) ==================

DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)


def normalize_domain(text: str) -> str | None:
    text = text.strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = text.split("/")[0].split("?")[0]
    if DOMAIN_RE.match(text):
        return text
    return None


async def dns_handler_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chỉ chạy trong private chat."""
    chat = update.effective_chat
    if chat.type != "private":
        return  # không xử lý ở group

    if not update.message or not update.message.text:
        return

    raw = update.message.text.strip()
    domain = normalize_domain(raw)
    if not domain:
        await update.message.reply_text("Không nhận ra domain hợp lệ. Ví dụ: google.com")
        return

    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5
    resolver.timeout = 5

    lines = [f"🔍 Kết quả DNS cho: *{domain}*\n"]

    # A records
    try:
        answers_a = resolver.resolve(domain, "A")
        ips = [rdata.address for rdata in answers_a]
        lines.append("📌 A records:")
        for ip in ips:
            lines.append(f"• {ip}")
    except Exception as e:
        lines.append(f"📌 A records: _không lấy được_ ({e.__class__.__name__})")

    # CNAME
    try:
        answers_c = resolver.resolve(domain, "CNAME")
        cnames = [str(rdata.target).rstrip(".") for rdata in answers_c]
        lines.append("\n🔗 CNAME records:")
        for c in cnames:
            lines.append(f"• {c}")
    except Exception:
        lines.append("\n🔗 CNAME records: _không có hoặc không lấy được_")

    await update.message.reply_markdown("\n".join(lines))


# ================== HELP COMMAND ==================

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type in ("group", "supergroup"):
        await update.message.reply_markdown(HELP_TEXT_GROUP)
    else:
        await update.message.reply_markdown(HELP_TEXT_PRIVATE)


# ================== MAIN ==================

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN chưa được cấu hình.")

    init_db()

    app = Application.builder().token(token).build()

    # --- LỆNH CHUNG (group + private) ---
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    # --- CHI TIÊU: CHỈ GROUP ---
    app.add_handler(
        CommandHandler(
            "add",
            add_expense_cmd,
            filters=filters.ChatType.GROUPS,
        )
    )
    app.add_handler(
        CommandHandler(
            "today",
            today_cmd,
            filters=filters.ChatType.GROUPS,
        )
    )
    app.add_handler(
        CommandHandler(
            "month",
            month_cmd,
            filters=filters.ChatType.GROUPS,
        )
    )

    # --- DNS: CHỈ PRIVATE ---
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            dns_handler_private,
        )
    )

    logger.info("Bot started…")
    app.run_polling()


if __name__ == "__main__":
    main()
