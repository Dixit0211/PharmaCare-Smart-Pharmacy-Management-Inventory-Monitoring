"""Configuration management using environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application configuration and constants."""

    APP_NAME: str = os.getenv("APP_NAME", "PharmaCare")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "pharmacare-insecure-default-key-2026")

    # Database URL: defaults to local sqlite database in data/ directory
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'pharmacare.db'}")

    # Security & Session
    SESSION_EXPIRE_MINUTES: int = int(os.getenv("SESSION_EXPIRE_MINUTES", "480"))
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))

    # Business Defaults
    EXPIRY_ALERT_DAYS_DEFAULT: int = int(os.getenv("EXPIRY_ALERT_DAYS_DEFAULT", "30"))
    MIN_STOCK_THRESHOLD_DEFAULT: int = int(os.getenv("MIN_STOCK_THRESHOLD_DEFAULT", "15"))
    DEFAULT_TAX_RATE: float = float(os.getenv("DEFAULT_TAX_RATE", "5.0"))
    DEFAULT_INVOICE_PREFIX: str = os.getenv("DEFAULT_INVOICE_PREFIX", "INV-PHARMA")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", str(BASE_DIR / "logs" / "pharmacare.log"))

    # Asset & data paths
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    ASSETS_DIR: Path = BASE_DIR / "assets"
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    INVOICES_DIR: Path = BASE_DIR / "invoices"
    BACKUPS_DIR: Path = BASE_DIR / "backups"
    LOGO_PATH: Path = ASSETS_DIR / "logo.svg"

    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        for path in [
            self.DATA_DIR,
            self.LOGS_DIR,
            self.ASSETS_DIR,
            self.UPLOADS_DIR,
            self.INVOICES_DIR,
            self.BACKUPS_DIR,
        ]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
