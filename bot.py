import os
import sqlite3
import csv
import io
from datetime import datetime, date

import httpx
from telegram import Update, Chat
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Lấy token từ biến môi trường trên Render
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong Environment Variables")

DB_PATH = "expenses.db"


# ==========================
#   PHẦN DB CHI TIÊU
# ==========================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            amount INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def add_expense_db(chat_id: int, user_id: int, username: str, amount: int, note: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO expenses (chat_id, user_id, username, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            chat_id,
            user_id,
            username,
            amount,
            note,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def sum_expenses_db(chat_id: int, mode: str = "today") -> int:
    """
    mode = today | month | all
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if mode == "today":
        start = date.today().isoformat()
        end = start + "T23:59:59"
        c.execute(
            """
            SELECT SUM(amount) FROM expenses
            WHERE chat_id = ? AND created_at BETWEEN ? AND ?
            """,
            (chat_id, start, end),
        )
    elif mode == "month":
        today = date.today()
        start = today.replace(day=1).isoformat()
        # không cần end chính xác, chỉ cần lớn hơn mọi ngày trong tháng
        end = f"{today.year}-{today.month:02d}-31T23:59:59"
        c.execute(
            """
            SELECT SUM(amount) FROM expenses
            WHERE chat_id = ? AND created_at BETWEEN ? AND ?
            """,
            (chat_id, start, end),
        )
    else:  # all
        c.execute(
            """
            SELECT SUM(amount) FROM expenses
            WHERE chat_id = ?
            """,
            (chat_id,),
        )

    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0


def export_expenses_db(chat_id: int) -> io.BytesIO:
    """
    Export về CSV (Excel mở được bình thường)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT created_at, username, amount, note
        FROM expenses
        WHERE chat_id = ?
        ORDER BY created_at ASC
        """,
        (chat_id,),
    )
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Thời gian (UTC)", "Người nhập", "Số tiền", "Ghi chú"])
    for created_at, username, amount, note in rows:
        writer.writerow([created_at, username or "", amount, note or ""])

    data = io.BytesIO(output.getvalue().encode("utf-8"))
    data.name = "chi_tieu.csv"
    return data


# ==========================
#   HELPER PARSE SỐ TIỀN
# ==========================

def parse_amount(text: str) -> int | None:
    """
    Hỗ trợ các kiểu:
    - 200000
    - 200k / 200K  -> 200 * 1000
    - 200.000      -> 200000
    """
    text = text.replace(".", "").replace(",", "").strip().lower()
    if not text:
        return None

    if text.endswith("k"):
        try:
            base = int(text[:-1])
            return base * 1000
        except ValueError:
            return None

    try:
        return int(text)
    except ValueError:
        return None


# ==========================
#   HANDLER CHUNG
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat: Chat = update.effective_chat
    if chat.type in ("group", "supergroup"):
        msg = (
            "👋 Xin chào mọi người!\n\n"
            "Tao là bot **chi tiêu + DNS**.\n\n"
            "💸 *Trong nhóm* tao làm chi tiêu:\n"
            "  • /add 200k ăn sáng\n"
            "  • /total – tổng hôm nay\n"
            "  • /total month – tổng tháng này\n"
            "  • /total all – tổng mọi thời gian\n"
            "  • /export – xuất file CSV mở bằng Excel\n\n"
            "💬 Nhắn riêng tao để dùng chức năng DNS:\n"
            "  • /dns example.com\n"
            "  • /cname example.com\n"
        )
    else:
        msg = (
            "👋 Xin chào!\n\n"
            "💸 Vào *nhóm gia đình* để dùng chức năng chi tiêu.\n"
            "💻 Ở đây (chat riêng) tao hỗ trợ kiểm tra DNS:\n"
            "  • /dns example.com – xem bản ghi A\n"
            "  • /cname example.com – xem bản ghi CNAME\n"
        )
    await update.message.reply_markdown(msg)


# ==========================
#   CHI TIÊU (GROUP)
# ==========================

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh chi tiêu chỉ dùng trong nhóm nha.")
        return

    if not context.args:
        await update.message.reply_text("Dùng: /add [số tiền] [ghi chú]\nVí dụ: /add 200k ăn sáng")
        return

    amount_str = context.args[0]
    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    amount = parse_amount(amount_str)
    if amount is None or amount <= 0:
        await update.message.reply_text("Số tiền không hợp lệ. Ví dụ: 200000 hoặc 200k")
        return

    user = update.effective_user
    add_expense_db(
        chat_id=chat.id,
        user_id=user.id,
        username=user.full_name,
        amount=amount,
        note=note,
    )

    await update.message.reply_text(
        f"✅ Đã ghi: {amount:,} đ"
        + (f" – {note}" if note else "")
    )


async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh /total chỉ dùng trong nhóm.")
        return

    mode = "today"
    if context.args:
        arg = context.args[0].lower()
        if arg in ["month", "thang", "tháng"]:
            mode = "month"
        elif arg in ["all", "tatca", "tấtcả"]:
            mode = "all"

    total_amount = sum_expenses_db(chat.id, mode=mode)
    if mode == "today":
        label = "hôm nay"
    elif mode == "month":
        label = "tháng này"
    else:
        label = "từ trước tới giờ"

    await update.message.reply_text(
        f"💰 Tổng chi {label}: {total_amount:,} đ"
    )


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Lệnh /export chỉ dùng trong nhóm.")
        return

    file_data = export_expenses_db(chat.id)
    await update.message.reply_document(
        document=file_data,
        filename=file_data.name,
        caption="📂 File chi tiêu (CSV – mở bằng Excel được).",
    )


# ==========================
#   DNS / CNAME (PRIVATE)
# ==========================

async def dns_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("private",):
        await update.message.reply_text("Lệnh DNS dùng khi nhắn riêng với bot nha.")
        return

    if not context.args:
        await update.message.reply_text("Dùng: /dns example.com")
        return

    domain = context.args[0].strip()
    if not domain:
        await update.message.reply_text("Domain không hợp lệ.")
        return

    url = "https://dns.google/resolve"
    params = {"name": domain, "type": "A"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as e:
        await update.message.reply_text(f"Lỗi gọi DNS: {e}")
        return

    answers = data.get("Answer")
    if not answers:
        await update.message.reply_text(f"Không tìm thấy bản ghi A cho {domain}")
        return

    lines = [f"🔎 A record cho *{domain}*:"]
    for ans in answers:
        if ans.get("type") == 1:  # A
            lines.append(f"• {ans.get('data')}")

    await update.message.reply_markdown("\n".join(lines) if len(lines) > 1 else f"Không có A record cho {domain}")


async def cname_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("private",):
        await update.message.reply_text("Lệnh CNAME dùng khi nhắn riêng với bot nha.")
        return

    if not context.args:
        await update.message.reply_text("Dùng: /cname example.com")
        return

    domain = context.args[0].strip()
    if not domain:
        await update.message.reply_text("Domain không hợp lệ.")
        return

    url = "https://dns.google/resolve"
    params = {"name": domain, "type": "CNAME"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as e:
        await update.message.reply_text(f"Lỗi gọi DNS: {e}")
        return

    answers = data.get("Answer")
    if not answers:
        await update.message.reply_text(f"Không tìm thấy bản ghi CNAME cho {domain}")
        return

    lines = [f"🔎 CNAME record cho *{domain}*:"]
    for ans in answers:
        if ans.get("type") == 5:  # CNAME
            lines.append(f"• {ans.get('data')}")

    await update.message.reply_markdown("\n".join(lines))


# ==========================
#   MAIN
# ==========================

def main():
    # Khởi tạo DB
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # Lệnh chung
    app.add_handler(CommandHandler("start", start))

    # Chi tiêu (group)
    app.add_handler(CommandHandler("add", add_expense))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("export", export_csv))

    # DNS (private)
    app.add_handler(CommandHandler("dns", dns_lookup))
    app.add_handler(CommandHandler("cname", cname_lookup))

    # Chạy polling – KHÔNG dùng asyncio.run nữa
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
