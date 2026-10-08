"""String, currency, date, and number formatting helpers."""

from typing import Union, Optional
from datetime import date, datetime


def format_currency(amount: Union[float, int, None]) -> str:
    """Format numeric value into Indian Rupee currency string."""
    if amount is None:
        return "₹0.00"
    try:
        val = float(amount)
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return f"₹{amount}"


def format_date(d: Union[date, datetime, str, None], fmt: str = "%d %b %Y") -> str:
    """Format date into standard readable format (e.g. 15 Oct 2026)."""
    if d is None:
        return "-"
    if isinstance(d, datetime):
        return d.strftime(fmt)
    if isinstance(d, date):
        return d.strftime(fmt)
    if isinstance(d, str):
        try:
            parsed = datetime.fromisoformat(d.replace("Z", "+00:00"))
            return parsed.strftime(fmt)
        except Exception:
            return d
    return str(d)


def format_datetime(dt: Union[datetime, str, None], fmt: str = "%d %b %Y, %I:%M %p") -> str:
    """Format timestamp into readable datetime string."""
    if dt is None:
        return "-"
    if isinstance(dt, datetime):
        return dt.strftime(fmt)
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return parsed.strftime(fmt)
        except Exception:
            return dt
    return str(dt)


def format_number(num: Union[int, float, None]) -> str:
    """Format integers or counts with thousands separators."""
    if num is None:
        return "0"
    try:
        val = int(num)
        return f"{val:,}"
    except (ValueError, TypeError):
        return str(num)


def format_phone(phone: Optional[str]) -> str:
    """Standardize phone string display."""
    if not phone:
        return "-"
    clean = phone.strip()
    return clean
