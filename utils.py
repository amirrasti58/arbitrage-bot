"""
============================================================
utils.py
‎ابزارهای عمومی مشترک بین ماژول‌های دیگر

‎شامل:
‎- فرمت‌دهی اعداد (تومان، درصد، تتر)
‎- کار با زمان (تهران / UTC)
‎- نرمال‌سازی ارقام فارسی/عربی
‎- لاگ ساده و یکدست

‎هیچ منطق آربیتراژ، SQLite یا Telegram اینجا نباید باشد.
============================================================
"""

import sys
import traceback
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # پایتون خیلی قدیمی - نباید در عمل رخ دهد
    ZoneInfo = None

from config import TIMEZONE_NAME


# ============================================================
‎# منطقه زمانی
# ============================================================

def get_timezone():
    """
    ZoneInfo تهران را برمی‌گرداند.

‎    اگر tzdata روی سیستم نصب نباشد (مثلاً برخی ایمیج‌های
‎    داکر خیلی سبک)، یک خطای واضح و قابل‌فهم پرتاب می‌کند
‎    به‌جای یک traceback گنگ در وسط اجرای برنامه.
    """

    if ZoneInfo is None:
        raise RuntimeError(
‎            "ماژول zoneinfo در دسترس نیست. "
‎            "پایتون ۳.۹ یا بالاتر لازم است."
        )

    try:
        return ZoneInfo(TIMEZONE_NAME)

    except Exception as e:

        raise RuntimeError(
            f"منطقه زمانی '{TIMEZONE_NAME}' قابل بارگذاری نیست. "
            f"به احتمال زیاد پکیج 'tzdata' نصب نشده است. "
            f"دستور نصب: pip install tzdata --break-system-packages "
            f"(خطای اصلی: {e})"
        ) from e


_TEHRAN_TZ = None


def tehran_tz():
    """
‎    نمونه‌ی cache‌شده‌ی ZoneInfo تهران.
‎    از ساخت مجدد آن در هر فراخوانی جلوگیری می‌کند.
    """

    global _TEHRAN_TZ

    if _TEHRAN_TZ is None:
        _TEHRAN_TZ = get_timezone()

    return _TEHRAN_TZ


def now_tehran():
‎    """زمان فعلی به وقت تهران، به‌صورت datetime آگاه از تایم‌زون."""
    return datetime.now(tehran_tz())


def now_utc():
‎    """زمان فعلی UTC، به‌صورت datetime آگاه از تایم‌زون."""
    from datetime import timezone
    return datetime.now(timezone.utc)


def utc_iso(dt=None):
    """
‎    یک datetime را به رشته‌ی ISO 8601 UTC تبدیل می‌کند.
‎    اگر dt داده نشود، زمان فعلی استفاده می‌شود.
‎    این فرمت همان چیزی است که در ستون ts_utc دیتابیس ذخیره می‌شود.
    """

    if dt is None:
        dt = now_utc()

    from datetime import timezone

    if dt.tzinfo is None:
‎        # فرض: اگر tzinfo نداشت، از قبل UTC بوده
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_utc_iso(text):
    """
‎    رشته‌ی ذخیره‌شده با utc_iso() را به datetime آگاه از UTC برمی‌گرداند.
    """

    from datetime import timezone

    dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def tehran_date_str(dt=None):
‎    """تاریخ به فرمت YYYY-MM-DD به وقت تهران."""

    if dt is None:
        dt = now_tehran()
    else:
        dt = dt.astimezone(tehran_tz())

    return dt.strftime("%Y-%m-%d")


def tehran_time_hhmm(dt=None):
‎    """ساعت:دقیقه به فرمت HH:MM به وقت تهران."""

    if dt is None:
        dt = now_tehran()
    else:
        dt = dt.astimezone(tehran_tz())

    return dt.strftime("%H:%M")


def report_slot_id(date_str, time_str):
    """
‎    شناسه‌ی یکتای یک slot گزارش دوره‌ای می‌سازد.
‎    مثال: '2026-09-24T14:00'
    """

    return f"{date_str}T{time_str}"


# ============================================================
‎# فرمت‌دهی اعداد
# ============================================================

def format_toman(value):
‎    """نمایش یک عدد تومانی با جداکننده هزارگان، بدون اعشار."""

    if value is None:
        return "-"

    return f"{value:,.0f}"


def format_toman_signed(value):
    """
‎    نمایش عدد سود/زیان تومانی بدون علامت منفی جلوی عدد.

‎    مثبت: 143,371
‎    منفی: 143,371-

‎    علامت منفی عمداً پشت عدد قرار می‌گیرد (قرارداد نمایش پروژه).
    """

    if value is None:
        return "-"

    number = f"{abs(value):,.0f}"

    if value < 0:
        return f"{number}-"

    return number


def format_percent(value):
    """
‎    نمایش درصد با علامت منفی پشت عدد (نه جلوی آن).

‎    مثبت: 1.20%
‎    منفی: 0.03%-
    """

    if value is None:
        return "-"

    if value < 0:
        return f"{abs(value):.2f}%-"

    return f"{value:.2f}%"


def format_usdt(value):
‎    """نمایش مقدار تتر با یک رقم اعشار."""

    if value is None:
        return "-"

    return f"{abs(value):,.1f}"


def get_profit_indicator(value):
‎    """ایموجی وضعیت بر اساس مثبت/منفی/صفر بودن سود."""

    if value is None:
        return "⚪"

    if value < 0:
        return "🔴"

    if value > 0:
        return "🟢"

    return "⚪"


def get_profit_label(value):
‎    """برچسب متنی مناسب برای سود یا زیان."""

    if value is not None and value < 0:
        return "زیان خالص"

    if value is not None and value > 0:
        return "سود خالص"

    return "نتیجه خالص"


def get_profit_percent_label(value):
‎    """برچسب متنی مناسب برای درصد سود یا زیان."""

    if value is not None and value < 0:
        return "درصد زیان"

    if value is not None and value > 0:
        return "درصد سود"

    return "درصد نتیجه"


def format_profit_line(value):
‎    """یک خط کامل نمایش سود/زیان با ایموجی و برچسب مناسب."""

    indicator = get_profit_indicator(value)
    label = get_profit_label(value)
    amount = format_toman_signed(value)

    return f"{indicator} {label}: {amount} تومان"


def format_profit_percent_line(value):
‎    """یک خط کامل نمایش درصد سود/زیان با ایموجی و برچسب مناسب."""

    indicator = get_profit_indicator(value)
    label = get_profit_percent_label(value)
    percent = format_percent(value)

    return f"{indicator} {label}: {percent}"


# ============================================================
‎# نرمال‌سازی ارقام فارسی/عربی
# ============================================================

_DIGIT_MAP = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}


def normalize_digits(text):
‎    """ارقام فارسی و عربی را به ارقام لاتین تبدیل می‌کند."""

    result = str(text)

    for persian, latin in _DIGIT_MAP.items():
        result = result.replace(persian, latin)

    return result


def parse_toman_input(text):
    """
‎    ورودی کاربر برای مبلغ تومانی را parse می‌کند.
‎    ارقام فارسی، کاما و فاصله را پاک‌سازی می‌کند.
‎    در صورت نامعتبر بودن None برمی‌گرداند.
    """

    normalized = normalize_digits(text)

    cleaned = (
        normalized
        .replace(",", "")
        .replace("٬", "")
        .replace(" ", "")
    )

    try:
        amount = int(cleaned)
    except ValueError:
        return None

    if amount <= 0:
        return None

    return amount


def parse_percent_input(text):
    """
‎    ورودی کاربر برای درصد حد هشدار را parse می‌کند.
‎    در صورت نامعتبر بودن یا خارج از بازه (0, 100]، None برمی‌گرداند.
    """

    normalized = normalize_digits(text)

    cleaned = (
        normalized
        .replace(",", ".")
        .replace("٬", ".")
        .replace("٫", ".")
        .replace("%", "")
        .replace("٪", "")
        .replace(" ", "")
    )

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if value <= 0 or value > 100:
        return None

    return value


# ============================================================
‎# لاگ ساده
# ============================================================

def log(message):
‎    """چاپ یک خط لاگ با timestamp تهران، برای یکدستی در کل پروژه."""

    try:
        stamp = now_tehran().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        stamp = "??:??:??"

    print(f"[{stamp}] {message}", flush=True)


def log_error(context, exc):
    """
‎    لاگ یک خطا همراه با context مشخص و traceback کامل روی stderr،
‎    بدون متوقف کردن برنامه. برای خطاهایی که باید ثبت شوند ولی
‎    نباید کل حلقه اصلی را بخوابانند (مثل خطای persistence یا یک
‎    صرافی خاص).
    """

    log(f"⚠️ خطا در {context}: {exc}")

    traceback.print_exc(file=sys.stderr)
