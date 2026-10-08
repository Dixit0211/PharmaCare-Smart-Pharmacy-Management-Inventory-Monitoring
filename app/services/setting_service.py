"""Pharmacy metadata and configuration settings service."""

from typing import Dict, Any, Optional
from sqlalchemy import select
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.models.setting import AppSetting
from app.services.auth_service import require_role
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SETTINGS = {
    "pharmacy_name": "PharmaCare Hospital Pharmacy",
    "pharmacy_address": "402 Medical Enclave, Hospital Road, Metro City - 400001",
    "pharmacy_phone": "+91 98765 43210",
    "pharmacy_email": "dispensary@pharmacare.local",
    "pharmacy_dl_no": "DL-2024-MH-99881",
    "pharmacy_gstin": "27AAAAA0000A1Z5",
    "default_gst_rate": "5.0",
    "expiry_warning_days": "30",
    "default_min_stock": "15",
    "invoice_footer_note": "Medicines sold are non-refundable. Take as advised by registered medical practitioner.",
}


class SettingService:
    """Manages application key-value configuration and pharmacy metadata."""

    @staticmethod
    def get_all_settings() -> Dict[str, str]:
        """Fetch all configuration settings, applying defaults for any missing keys."""
        settings = dict(DEFAULT_SETTINGS)
        with get_db() as session:
            rows = session.scalars(select(AppSetting)).all()
            for r in rows:
                settings[r.key] = r.value
        return settings

    @staticmethod
    def get_setting(key: str, default: Optional[str] = None) -> str:
        """Fetch a specific setting value by key."""
        with get_db() as session:
            setting = session.scalars(
                select(AppSetting).where(AppSetting.key == key)
            ).first()
            if setting:
                return setting.value
            return default if default is not None else DEFAULT_SETTINGS.get(key, "")

    @staticmethod
    @require_role("admin")
    def update_settings(current_user: Dict[str, Any], settings_data: Dict[str, str]) -> Dict[str, str]:
        """Update pharmacy configuration and business rules."""
        if not settings_data:
            raise ValidationError("No settings data provided.")

        updated_keys = []
        with get_db() as session:
            for key, val in settings_data.items():
                str_val = str(val).strip()
                setting = session.scalars(
                    select(AppSetting).where(AppSetting.key == key)
                ).first()

                if setting:
                    if setting.value != str_val:
                        setting.value = str_val
                        updated_keys.append(key)
                else:
                    new_setting = AppSetting(
                        key=key,
                        value=str_val,
                        description=f"Configuration parameter for {key}",
                    )
                    session.add(new_setting)
                    updated_keys.append(key)

            session.commit()

        if updated_keys:
            AuditService.log_action(
                user_id=current_user.get("id"),
                username=current_user.get("username", "admin"),
                action="UPDATE",
                module="SETTINGS",
                description=f"Updated pharmacy settings: {', '.join(updated_keys)}",
            )
            logger.info(f"Updated settings {updated_keys} by {current_user.get('username')}")

        return SettingService.get_all_settings()
