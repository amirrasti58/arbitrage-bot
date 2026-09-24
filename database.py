"""
============================================================
database.py
‎لایهی دیتابیس (SQLite)

‎مسئولیت این فایل:
‎- ساخت و مهاجرت schema
‎- مدیریت connection (هر Thread، connection خودش را میسازد)
- WAL mode + checkpoint
‎- تمام عملیات insert/update/query روی جداول

‎این فایل هیچ چیزی دربارهی Telegram، صرافیها، یا GitHub
Actions نمیداند. فقط SQLite.

‎جداول:
- opportunities            : تاریخچهی فرصتهای واجد شرایط
- stats_totals              : شمارندههای تجمعی (یک ردیف ثابت)
- stats_daily                : شمارندههای روزانه (به وقت تهران)
- periodic_reports_sent     : ردیابی گزارشهای دورهای برای catch-up
============================================================
"""

import sqlite3
import threading

from config import DATABASE_PATH
from utils import log, log_error, utc_iso


# ============================================================
# Schema
# ============================================================

SCHEMA_STATEMENTS = [

    """
    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_utc TEXT NOT NULL,

        buy_exchange TEXT NOT NULL,
        sell_exchange TEXT NOT NULL,

        capital_toman INTEGER NOT NULL,
        spent_toman INTEGER NOT NULL,
        usdt_amount REAL NOT NULL,
        received_toman INTEGER NOT NULL,
        net_profit_toman INTEGER NOT NULL,
        profit_percent REAL NOT NULL,

        buy_price REAL NOT NULL,
        sell_price REAL NOT NULL,

        buy_fee REAL NOT NULL,
        sell_fee REAL NOT NULL,

        buy_levels INTEGER NOT NULL,
        sell_levels INTEGER NOT NULL,

        buy_fill_ratio REAL NOT NULL,
        sell_fill_ratio REAL NOT NULL,
        execution_ratio REAL NOT NULL,

        alert_sent INTEGER NOT NULL DEFAULT 0
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_opportunities_ts "
    "ON opportunities(ts_utc)",

    "CREATE INDEX IF NOT EXISTS idx_opportunities_route "
    "ON opportunities(buy_exchange, sell_exchange, ts_utc)",

    """
    CREATE TABLE IF NOT EXISTS stats_totals (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_route_checks INTEGER NOT NULL DEFAULT 0,
        total_cycles INTEGER NOT NULL DEFAULT 0,
        total_positive_routes INTEGER NOT NULL DEFAULT 0,
        total_qualified_opportunities INTEGER NOT NULL DEFAULT 0,
        total_alerts_sent INTEGER NOT NULL DEFAULT 0,
        total_simulated_profit_toman INTEGER NOT NULL DEFAULT 0,
        total_api_errors INTEGER NOT NULL DEFAULT 0
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS stats_daily (
        date TEXT PRIMARY KEY,
        route_checks INTEGER NOT NULL DEFAULT 0,
        positive_routes INTEGER NOT NULL DEFAULT 0,
        qualified INTEGER NOT NULL DEFAULT 0,
        alerts INTEGER NOT NULL DEFAULT 0,
        simulated_profit_toman INTEGER NOT NULL DEFAULT 0
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS periodic_reports_sent (
        report_slot TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        created_at_utc TEXT NOT NULL
    )
    """,
]


# ============================================================
‎# مدیریت Connection
# ============================================================
#
‎# هر Thread باید connection خودش را بسازد (نه به اشتراک بگذارد).
‎# این یعنی check_same_thread=False لازم نیست: پیشفرض ایمنتر
# SQLite همین است که هر connection فقط در Thread خودش استفاده شود.
#
# _thread_local یک نمونهی per-thread نگه میدارد تا در طول یک
# Thread، بارها connection جدید ساخته نشود.

_thread_local = threading.local()


def _configure_connection(conn):
‎    """تنظیمات استاندارد هر connection تازهساز."""

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_connection():
    """
    connection مخصوص Thread فعلی را برمیگرداند.
‎    اگر وجود نداشته باشد، میسازد.
    """

    conn = getattr(_thread_local, "conn", None)

    if conn is None:
        conn = sqlite3.connect(DATABASE_PATH, timeout=30)
        conn = _configure_connection(conn)
        _thread_local.conn = conn

    return conn


def close_connection():
    """connection مربوط به Thread فعلی را میبندد (در صورت وجود)."""

    conn = getattr(_thread_local, "conn", None)

    if conn is not None:
        try:
            conn.close()
        except Exception as e:
            log_error("close_connection", e)
        _thread_local.conn = None


def initialize_database():
    """
    Schema را میسازد (اگر وجود نداشته باشد) و
‎    ردیف اولیهی stats_totals را تضمین میکند.
‎    باید در ابتدای main.py و همچنین در ابتدای Telegram thread
‎    (برای connection خودش) صدا زده شود.
    """

    conn = get_connection()

    with conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)

        conn.execute(
            "INSERT OR IGNORE INTO stats_totals (id) VALUES (1)"
        )

    log("🗄 دیتابیس آماده شد (schema + WAL).")


def checkpoint(mode="FULL"):
    """
    WAL checkpoint را اجرا میکند تا تغییرات از فایل -wal
‎    به فایل اصلی دیتابیس منتقل شوند.

‎    این تابع باید قبل از هر آپلود/کپی فایل دیتابیس به بیرون
‎    (مثلاً persistence.py) صدا زده شود، وگرنه ممکن است بخشی
‎    از دادههای تازه در فایل اصلی نباشند.

    mode: 'PASSIVE' | 'FULL' | 'RESTART' | 'TRUNCATE'
‎    برای checkpoint نهایی قبل از خروج، TRUNCATE ایمنترین
‎    انتخاب است چون فایل -wal را هم خالی میکند.
    """

    conn = get_connection()

    try:
        conn.execute(f"PRAGMA wal_checkpoint({mode})")
        log(f"💾 WAL checkpoint ({mode}) انجام شد.")
        return True

    except Exception as e:
        log_error("checkpoint", e)
        return False


# ============================================================
# Opportunities (تاریخچه)
# ============================================================

def insert_opportunity(record):
    """
‎    یک فرصت واجد شرایط را در جدول opportunities ثبت میکند و
‎    همزمان شمارندههای stats_totals و stats_daily مربوطه را
‎    در همان transaction بهروزرسانی میکند (اتمیک).

    record باید یک dict با کلیدهای زیر باشد:
    ts_utc, buy_exchange, sell_exchange, capital_toman,
    spent_toman, usdt_amount, received_toman, net_profit_toman,
    profit_percent, buy_price, sell_price, buy_fee, sell_fee,
    buy_levels, sell_levels, buy_fill_ratio, sell_fill_ratio,
    execution_ratio

‎    خروجی: id رکورد ثبتشده.

‎    توجه: این تابع خودش Network I/O (تلگرام) انجام نمیدهد.
‎    علامتگذاری alert_sent جداگانه و بعد از ارسال موفق پیام
‎    با mark_alert_sent() انجام میشود.
    """

    conn = get_connection()
    today = record["ts_utc"][:10]  # این UTC است؛ فراخوان باید
‎    # تاریخ تهران را جدا محاسبه و بهعنوان daily_date بدهد.
    daily_date = record["daily_date"]

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO opportunities (
                ts_utc, buy_exchange, sell_exchange,
                capital_toman, spent_toman, usdt_amount,
                received_toman, net_profit_toman, profit_percent,
                buy_price, sell_price, buy_fee, sell_fee,
                buy_levels, sell_levels,
                buy_fill_ratio, sell_fill_ratio, execution_ratio,
                alert_sent
            ) VALUES (
                :ts_utc, :buy_exchange, :sell_exchange,
                :capital_toman, :spent_toman, :usdt_amount,
                :received_toman, :net_profit_toman, :profit_percent,
                :buy_price, :sell_price, :buy_fee, :sell_fee,
                :buy_levels, :sell_levels,
                :buy_fill_ratio, :sell_fill_ratio, :execution_ratio,
                0
            )
            """,
            record,
        )

        opportunity_id = cursor.lastrowid

        conn.execute(
            """
            UPDATE stats_totals SET
                total_qualified_opportunities =
                    total_qualified_opportunities + 1,
                total_simulated_profit_toman =
                    total_simulated_profit_toman + :net_profit
            WHERE id = 1
            """,
            {"net_profit": record["net_profit_toman"]},
        )

        _ensure_daily_row(conn, daily_date)

        conn.execute(
            """
            UPDATE stats_daily SET
                qualified = qualified + 1,
                simulated_profit_toman =
                    simulated_profit_toman + :net_profit
            WHERE date = :date
            """,
            {
                "net_profit": record["net_profit_toman"],
                "date": daily_date,
            },
        )

    return opportunity_id


def mark_alert_sent(opportunity_id):
    """
‎    بعد از ارسال موفق پیام تلگرام صدا زده میشود.
‎    خارج از transaction اصلی insert_opportunity قرار دارد
‎    چون HTTP request بین آن دو فاصله انداخته است.

‎    نکته: اگر برنامه دقیقاً بین ارسال موفق تلگرام و این UPDATE
‎    از کار بیفتد، رکورد با alert_sent=0 باقی میماند در حالی
‎    که پیام واقعاً ارسال شده است. این یک edge case شناختهشده
‎    و پذیرفتهشده است (مستند در طراحی پروژه)، نه یک باگ.
    """

    conn = get_connection()

    with conn:
        conn.execute(
            "UPDATE opportunities SET alert_sent = 1 WHERE id = ?",
            (opportunity_id,),
        )

        conn.execute(
            """
            UPDATE stats_totals SET
                total_alerts_sent = total_alerts_sent + 1
            WHERE id = 1
            """
        )


def mark_alert_sent_for_today(daily_date):
‎    """شمارندهی alerts روزانه را یک واحد افزایش میدهد."""

    conn = get_connection()

    with conn:
        _ensure_daily_row(conn, daily_date)

        conn.execute(
            "UPDATE stats_daily SET alerts = alerts + 1 WHERE date = ?",
            (daily_date,),
        )


def get_last_opportunity_for_route(buy_exchange, sell_exchange):
    """
‎    آخرین رکورد ثبتشده برای یک مسیر مشخص را برمیگرداند
‎    (یا None). عمدتاً برای نمایش/دیباگ استفاده میشود؛ منطق
    dedupe اصلی در RAM (main.py) انجام میشود، نه با query زدن
‎    به این تابع در هر چرخه.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT * FROM opportunities
        WHERE buy_exchange = ? AND sell_exchange = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (buy_exchange, sell_exchange),
    ).fetchone()

    return dict(row) if row else None


def get_opportunities_by_date_range(start_date, end_date):
    """
‎    رکوردهای بین دو تاریخ (بر اساس daily_date تهران که در
    ts_utc قابل استخراج مستقیم نیست) را برمیگرداند.

‎    چون ts_utc به UTC ذخیره شده و تاریخ تهران ممکن است با
‎    تاریخ UTC یک روز اختلاف داشته باشد، این تابع بر اساس یک
‎    بازهی UTC (که فراخوان از قبل تبدیل کرده) فیلتر میکند.

    start_utc_iso / end_utc_iso: رشتههای ISO UTC (utc_iso()).
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT * FROM opportunities
        WHERE ts_utc >= ? AND ts_utc < ?
        ORDER BY id DESC
        """,
        (start_date, end_date),
    ).fetchall()

    return [dict(row) for row in rows]


def get_all_time_history_stats():
    """
‎    خلاصهی آماری کل تاریخچهی opportunities را برمیگرداند:
‎    تعداد، مجموع سود، میانگین درصد، بهترین رکورد، پرتکرارترین مسیر.

‎    توجه: این روی کل جدول opportunities محاسبه میشود (نه محدود
‎    به HISTORY_DISPLAY_LIMIT)، پس با total_qualified_opportunities
‎    در stats_totals باید همیشه برابر باشد (چون هر INSERT دقیقاً
‎    یک بار در هر دو جا شمرده میشود).
    """

    conn = get_connection()

    summary = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(net_profit_toman), 0) AS total_profit,
            COALESCE(AVG(profit_percent), 0) AS avg_percent
        FROM opportunities
        """
    ).fetchone()

    if summary["total"] == 0:
        return {
            "total": 0,
            "total_profit": 0,
            "avg_percent": 0,
            "best_record": None,
            "most_common_route": None,
            "most_common_route_count": 0,
        }

    best_row = conn.execute(
        """
        SELECT * FROM opportunities
        ORDER BY net_profit_toman DESC
        LIMIT 1
        """
    ).fetchone()

    route_row = conn.execute(
        """
        SELECT buy_exchange, sell_exchange, COUNT(*) AS cnt
        FROM opportunities
        GROUP BY buy_exchange, sell_exchange
        ORDER BY cnt DESC
        LIMIT 1
        """
    ).fetchone()

    return {
        "total": summary["total"],
        "total_profit": summary["total_profit"],
        "avg_percent": summary["avg_percent"],
        "best_record": dict(best_row) if best_row else None,
        "most_common_route": (
            f"{route_row['buy_exchange']} → {route_row['sell_exchange']}"
            if route_row else None
        ),
        "most_common_route_count": route_row["cnt"] if route_row else 0,
    }


# ============================================================
# Stats
# ============================================================

def _ensure_daily_row(conn, date_str):
    """
‎    ردیف مربوط به یک روز را در stats_daily تضمین میکند.
‎    باید همیشه داخل یک transaction باز صدا زده شود (conn.execute
‎    مستقیم، نه با کانتکست with conn جدید) تا اتمیک بماند.
    """

    conn.execute(
        "INSERT OR IGNORE INTO stats_daily (date) VALUES (?)",
        (date_str,),
    )


def record_cycle(route_count, positive_count, daily_date):
    """
‎    در پایان هر چرخهی محاسبه صدا زده میشود:
‎    شمارندههای کلی چرخه، تعداد route بررسیشده، و تعداد
    routeهای مثبت (سودده قبل از رسیدن به آستانهی هشدار) را
‎    بهروزرسانی میکند.

‎    توجه معنایی: positive_count یعنی تعداد routeهایی که
    net_profit >= MIN_NET_PROFIT_TOMAN بودند، نه تعداد
‎    چرخههایی که حداقل یک فرصت مثبت داشتند.
    """

    conn = get_connection()

    with conn:
        conn.execute(
            """
            UPDATE stats_totals SET
                total_cycles = total_cycles + 1,
                total_route_checks = total_route_checks + :routes,
                total_positive_routes =
                    total_positive_routes + :positive
            WHERE id = 1
            """,
            {"routes": route_count, "positive": positive_count},
        )

        _ensure_daily_row(conn, daily_date)

        conn.execute(
            """
            UPDATE stats_daily SET
                route_checks = route_checks + :routes,
                positive_routes = positive_routes + :positive
            WHERE date = :date
            """,
            {
                "routes": route_count,
                "positive": positive_count,
                "date": daily_date,
            },
        )


def record_api_error():
‎    """شمارندهی خطاهای API صرافیها را یک واحد افزایش میدهد."""

    conn = get_connection()

    with conn:
        conn.execute(
            """
            UPDATE stats_totals SET
                total_api_errors = total_api_errors + 1
            WHERE id = 1
            """
        )


def get_totals():
‎    """ردیف کامل stats_totals را بهصورت dict برمیگرداند."""

    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM stats_totals WHERE id = 1"
    ).fetchone()

    return dict(row) if row else {}


def get_daily_stats(date_str):
‎    """آمار یک روز مشخص را برمیگرداند (یا مقادیر صفر اگر ثبت نشده)."""

    conn = get_connection()

    row = conn.execute(
        "SELECT * FROM stats_daily WHERE date = ?",
        (date_str,),
    ).fetchone()

    if row:
        return dict(row)

    return {
        "date": date_str,
        "route_checks": 0,
        "positive_routes": 0,
        "qualified": 0,
        "alerts": 0,
        "simulated_profit_toman": 0,
    }


# ============================================================
# Periodic Report Slots (Catch-up)
# ============================================================

def get_consumed_report_slots(slot_ids):
    """
‎    از میان لیست slot_idهای دادهشده، آنهایی که قبلاً در جدول
‎    ثبت شدهاند (چه sent چه consumed) را بهصورت set برمیگرداند.
    """

    if not slot_ids:
        return set()

    conn = get_connection()

    placeholders = ",".join("?" for _ in slot_ids)

    rows = conn.execute(
        f"""
        SELECT report_slot FROM periodic_reports_sent
        WHERE report_slot IN ({placeholders})
        """,
        list(slot_ids),
    ).fetchall()

    return {row["report_slot"] for row in rows}


def consume_report_slots(slot_ids, sent_slot_id=None):
    """
‎    تمام slot_idهای دادهشده را در جدول ثبت میکند (در یک
    transaction اتمیک) تا دیگر هرگز دوباره پردازش نشوند.

    slot_idای که واقعاً پیام Telegram برایش ارسال شده،
‎    باید در sent_slot_id داده شود تا status آن 'sent' باشد؛
‎    بقیه با status='consumed' ثبت میشوند (یعنی از دست رفته
‎    و رد شده، بدون ارسال پیام).

‎    این تابع باید *قبل* از ارسال واقعی پیام تلگرام صدا زده
‎    نشود؛ ترتیب صحیح در main.py: ابتدا پیام ارسال شود (یا
‎    تلاش برای ارسال انجام شود)، سپس این تابع صدا زده شود -
‎    چون اگر برعکس باشد و ارسال شکست بخورد، slot به اشتباه
    consumed ثبت شده و دیگر هرگز retry نمیشود. اگر میخواهیم
‎    حتی در صورت شکست ارسال هم slot را consumed کنیم (برای
‎    جلوگیری از تلاشهای تکراری بیپایان)، این تصمیم آگاهانه
‎    در main.py گرفته میشود، نه اینجا.
    """

    if not slot_ids:
        return

    conn = get_connection()
    now = utc_iso()

    with conn:
        for slot_id in slot_ids:
            status = "sent" if slot_id == sent_slot_id else "consumed"

            conn.execute(
                """
                INSERT OR IGNORE INTO periodic_reports_sent
                    (report_slot, status, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (slot_id, status, now),
            )


def get_report_history(limit=20):
    """
‎    آخرین N رکورد گزارش دورهای را برمیگرداند (برای دیباگ/بازبینی).
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT * FROM periodic_reports_sent
        ORDER BY created_at_utc DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return [dict(row) for row in rows]
