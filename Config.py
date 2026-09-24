"""
============================================================
config.py
‎تنظیمات مرکزی ربات آربیتراژ

‎تمام مقادیر قابل‌تنظیم پروژه اینجا تعریف می‌شوند.
‎هیچ فایل دیگری نباید مستقیماً os.environ بخواند؛
‎همه باید از همین ماژول import کنند.
============================================================
"""

import os


# ============================================================
‎# کمکی برای خواندن متغیرهای محیطی با نوع مشخص
# ============================================================

def _env_str(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


# ============================================================
‎# صرافی‌ها
# ============================================================

ENABLED_EXCHANGES = ["Wallex", "BitPin", "Ramzinex"]

FEES = {
    "Wallex": {
        "maker": 0.0025,
        "taker": 0.0030,
    },
    "BitPin": {
        "maker": 0.0002,
        "taker": 0.0005,
    },
    "Ramzinex": {
        "maker": 0.0020,
        "taker": 0.0025,
    },
}

‎# نوع کارمزد مورد استفاده در محاسبات: maker یا taker
ORDER_TYPE = _env_str("ORDER_TYPE", "taker").lower()
if ORDER_TYPE not in ("maker", "taker"):
    ORDER_TYPE = "taker"

‎# نماد جفت‌ارز در هر صرافی
WALLEX_SYMBOL = "USDTTMN"
BITPIN_SYMBOL = "USDT_IRT"

‎# رمزینکس: pair_id به‌صورت پویا کشف می‌شود (به exchanges.py مراجعه شود).
‎# این‌جا فقط یک مقدار fallback برای حالتی که Discovery موقتاً شکست بخورد
‎# نگه‌داری می‌شود، صرفاً برای لاگ کردن هشدار، نه استفاده‌ی کورکورانه.
RAMZINEX_SYMBOL_HINT = "USDT/IRT"


# ============================================================
# Order Book و درخواست‌های شبکه
# ============================================================

REQUEST_TIMEOUT_SECONDS = _env_int("REQUEST_TIMEOUT_SECONDS", 15)
ORDERBOOK_LEVELS = _env_int("ORDERBOOK_LEVELS", 20)

‎# تلاش مجدد (Retry) با Exponential Backoff
RETRY_MAX_ATTEMPTS = _env_int("RETRY_MAX_ATTEMPTS", 4)
RETRY_BASE_DELAY_SECONDS = _env_float("RETRY_BASE_DELAY_SECONDS", 1.5)
RETRY_MAX_DELAY_SECONDS = _env_float("RETRY_MAX_DELAY_SECONDS", 20.0)

‎# کدهای HTTP که ارزش retry کردن دارند (خطاهای موقتی)
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

‎# کدهایی که هرگز نباید retry شوند (خطای درخواست، نه سرور)
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


# ============================================================
‎# آربیتراژ / تحلیل فرصت
# ============================================================

MIN_PROFIT_PERCENT_DEFAULT = _env_float("MIN_SPREAD_PERCENT", 1.0)

‎# حداقل سود خالص قابل‌اعتنا (تومان) - ثابت طراحی، نه قابل‌تغییر از Telegram
MIN_NET_PROFIT_TOMAN = _env_int("MIN_NET_PROFIT_TOMAN", 300_000)

MIN_EXECUTION_RATIO = _env_float("MIN_EXECUTION_RATIO", 0.80)
MAX_EXCHANGE_ALLOCATION_PERCENT = _env_float(
    "MAX_EXCHANGE_ALLOCATION_PERCENT", 0.70
)

DEFAULT_CAPITAL_TOMAN = _env_int("DEFAULT_CAPITAL_TOMAN", 50_000_000)

‎# تحلیل تاریخچه‌ی تحلیلی در RAM (نه SQLite) برای تخصیص سرمایه
OPPORTUNITY_HISTORY_LIMIT = _env_int("OPPORTUNITY_HISTORY_LIMIT", 120)
MIN_ALLOCATION_OBSERVATIONS = _env_int("MIN_ALLOCATION_OBSERVATIONS", 50)
MIN_POSITIVE_OBSERVATIONS = _env_int("MIN_POSITIVE_OBSERVATIONS", 3)


# ============================================================
# Dedupe / Cooldown (در RAM نگه‌داری می‌شوند)
# ============================================================

‎# حداقل فاصله بین دو ثبت تاریخچه برای همان مسیر (ثانیه)
HISTORY_DEDUPE_COOLDOWN_SECONDS = _env_int(
    "HISTORY_DEDUPE_COOLDOWN_SECONDS", 300
)

‎# حداقل فاصله بین دو هشدار Telegram برای همان مسیر (ثانیه)
ALERT_COOLDOWN_SECONDS = _env_int("ALERT_COOLDOWN_SECONDS", 60)


# ============================================================
‎# چرخه اجرا
# ============================================================

CHECK_INTERVAL_SECONDS = _env_int("CHECK_INTERVAL_SECONDS", 10)

‎# حداکثر زمان اجرای هر Run (ثانیه) - باید کمتر از سقف GitHub Actions باشد
‎# تا فرصت کافی برای safe-exit و checkpoint باقی بماند.
MAX_RUNTIME_SECONDS = _env_int("MAX_RUNTIME_SECONDS", 20_700)  # ~5.75 ساعت

‎# چند ثانیه قبل از پایان MAX_RUNTIME_SECONDS باید حلقه اصلی متوقف شود
‎# تا زمان کافی برای checkpoint/upload نهایی باقی بماند.
SHUTDOWN_GRACE_PERIOD_SECONDS = _env_int(
    "SHUTDOWN_GRACE_PERIOD_SECONDS", 60
)


# ============================================================
‎# منطقه زمانی
# ============================================================

TIMEZONE_NAME = "Asia/Tehran"


# ============================================================
‎# گزارش دوره‌ای
# ============================================================

‎# ساعات ارسال گزارش دوره‌ای (به وقت تهران، فرمت HH:MM)
REPORT_SLOT_TIMES = [
    "08:00", "10:00", "12:00", "14:00",
    "16:00", "18:00", "20:00", "22:00",
]

‎# بازه‌ای که ارسال گزارش دوره‌ای متوقف است (سکوت شبانه)
QUIET_HOURS_START = 23  # از این ساعت به بعد گزارش ارسال نمی‌شود
QUIET_HOURS_END = 8     # از این ساعت به بعد دوباره فعال می‌شود


# ============================================================
‎# پایگاه‌داده
# ============================================================

DATABASE_PATH = _env_str("DATABASE_PATH", "arbitrage.db")

‎# حداکثر تعداد رکورد نمایش‌داده‌شده در هر پیام تاریخچه Telegram
HISTORY_DISPLAY_LIMIT = _env_int("HISTORY_DISPLAY_LIMIT", 15)


# ============================================================
# Persistence (GitHub Actions Artifact)
# ============================================================

‎# نام ثابت artifact که برای نگهداری آخرین نسخه DB استفاده می‌شود
PERSISTENCE_ARTIFACT_NAME = _env_str(
    "PERSISTENCE_ARTIFACT_NAME", "arbitrage-db"
)

‎# فاصله‌ی checkpoint دوره‌ای در طول اجرا (ثانیه) - جدا از checkpoint پایانی
PERIODIC_CHECKPOINT_INTERVAL_SECONDS = _env_int(
    "PERIODIC_CHECKPOINT_INTERVAL_SECONDS", 3600
)

‎# مسیر فایلی که persistence.py برای اطلاع‌رسانی به لایه بیرونی
# (workflow) استفاده می‌کند تا بداند باید artifact جدید آپلود کند یا نه.
PERSISTENCE_SIGNAL_FILE = _env_str(
    "PERSISTENCE_SIGNAL_FILE", "persistence_ready.flag"
)


# ============================================================
# Telegram
# ============================================================

TELEGRAM_BOT_TOKEN = _env_str("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _env_str("TELEGRAM_CHAT_ID", "")

TELEGRAM_POLLING_TIMEOUT_SECONDS = _env_int(
    "TELEGRAM_POLLING_TIMEOUT_SECONDS", 20
)

‎# گزینه‌های آماده برای دکمه‌ی انتخاب موجودی (تومان)
CAPITAL_QUICK_OPTIONS = [
‎    (50_000_000, "۵۰ میلیون"),
‎    (100_000_000, "۱۰۰ میلیون"),
‎    (200_000_000, "۲۰۰ میلیون"),
‎    (500_000_000, "۵۰۰ میلیون"),
‎    (1_000_000_000, "۱ میلیارد"),
]

‎# گزینه‌های آماده برای دکمه‌ی انتخاب حد هشدار (درصد)
ALERT_THRESHOLD_QUICK_OPTIONS = [0.5, 1.0, 1.5, 2.0, 3.0]


# ============================================================
‎# اعتبارسنجی اولیه تنظیمات (fail-fast در صورت مقدار نامعتبر)
# ============================================================

def validate_config():
    """
‎    بررسی می‌کند تنظیمات حیاتی مقدار منطقی دارند.
‎    در صورت نامعتبر بودن، یک ValueError با پیام واضح ایجاد می‌کند
‎    تا خطا در همان ابتدای اجرا مشخص شود، نه وسط یک چرخه.
    """

    errors = []

    if CHECK_INTERVAL_SECONDS <= 0:
        errors.append("CHECK_INTERVAL_SECONDS باید مثبت باشد.")

    if MAX_RUNTIME_SECONDS <= SHUTDOWN_GRACE_PERIOD_SECONDS:
        errors.append(
            "MAX_RUNTIME_SECONDS باید بزرگ‌تر از "
            "SHUTDOWN_GRACE_PERIOD_SECONDS باشد."
        )

    if not (0 < MIN_EXECUTION_RATIO <= 1):
        errors.append("MIN_EXECUTION_RATIO باید بین ۰ و ۱ باشد.")

    if not (0 < MAX_EXCHANGE_ALLOCATION_PERCENT <= 1):
        errors.append(
            "MAX_EXCHANGE_ALLOCATION_PERCENT باید بین ۰ و ۱ باشد."
        )

    if DEFAULT_CAPITAL_TOMAN <= 0:
        errors.append("DEFAULT_CAPITAL_TOMAN باید مثبت باشد.")

    if MIN_NET_PROFIT_TOMAN < 0:
        errors.append("MIN_NET_PROFIT_TOMAN نمی‌تواند منفی باشد.")

    for exchange in ENABLED_EXCHANGES:
        if exchange not in FEES:
            errors.append(
                f"کارمزد صرافی {exchange} در FEES تعریف نشده است."
            )

    if errors:
        raise ValueError(
‎            "تنظیمات نامعتبر:\n" + "\n".join(f"- {e}" for e in errors)
        )
