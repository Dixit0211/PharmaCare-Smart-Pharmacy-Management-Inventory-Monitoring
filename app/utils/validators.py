"""Form and domain field validators."""

import re
from typing import Optional, Tuple
from datetime import date


def validate_email_format(email: Optional[str]) -> Tuple[bool, str]:
    """Validate email pattern format."""
    if not email:
        return False, "Email address is required"
    email = email.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, email):
        return False, "Please enter a valid email address (e.g., user@example.com)"
    return True, ""


def validate_phone_number(phone: Optional[str]) -> Tuple[bool, str]:
    """Validate 10-digit Indian phone format or international standard."""
    if not phone:
        return False, "Phone number is required"
    clean = re.sub(r"[\s\-\+\(\)]", "", phone.strip())
    if len(clean) < 10 or len(clean) > 13 or not clean.isdigit():
        return False, "Phone number must contain at least 10 valid numeric digits"
    return True, ""


def validate_positive_number(val: Optional[float], field_name: str = "Field", allow_zero: bool = False) -> Tuple[bool, str]:
    """Ensure numeric value is non-negative."""
    if val is None:
        return False, f"{field_name} is required"
    try:
        num = float(val)
        if allow_zero:
            if num < 0:
                return False, f"{field_name} must be 0 or greater"
        else:
            if num <= 0:
                return False, f"{field_name} must be strictly greater than 0"
        return True, ""
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"


def validate_date_not_past(d: Optional[date], field_name: str = "Date") -> Tuple[bool, str]:
    """Validate that date is today or in future."""
    if not d:
        return False, f"{field_name} is required"
    if d < date.today():
        return False, f"{field_name} cannot be in the past"
    return True, ""
