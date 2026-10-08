"""Pytest fixtures and isolated in-memory test database setup."""

import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Use an isolated SQLite file for testing
TEST_DB_PATH = BASE_DIR / "data" / "test_pharmacare.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

# Override DATABASE_URL before importing core modules
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.core.database import Base, init_db, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.category import Category
from app.models.setting import AppSetting
from app.services.setting_service import DEFAULT_SETTINGS


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create test database schema and seed baseline users and categories."""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    init_db()

    # Seed baseline Admin and Pharmacist
    with SessionLocal() as session:
        admin_user = User(
            username="admin_test",
            email="admin_test@pharmacare.local",
            password_hash=hash_password("Admin@123"),
            full_name="Dr. Test Admin",
            role="admin",
            phone="+91 98765 00001",
            is_active=True,
        )
        pharma_user = User(
            username="pharma_test",
            email="pharma_test@pharmacare.local",
            password_hash=hash_password("Pharma@123"),
            full_name="Test Pharmacist",
            role="pharmacist",
            phone="+91 98765 00002",
            is_active=True,
        )
        session.add_all([admin_user, pharma_user])

        # Baseline Categories
        cat1 = Category(name="Analgesics & Antipyretics", description="Pain and fever relief")
        cat2 = Category(name="Antibiotics", description="Antibacterial medications")
        cat3 = Category(name="Antihistamines", description="Allergy management")
        session.add_all([cat1, cat2, cat3])

        # Baseline Settings
        for k, v in DEFAULT_SETTINGS.items():
            session.add(AppSetting(key=k, value=v, description=f"Default {k}"))

        session.commit()

    yield

    # Teardown
    engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except Exception:
            pass


@pytest.fixture
def admin_user_payload():
    """Return dictionary payload representing logged-in administrator."""
    return {
        "id": 1,
        "username": "admin_test",
        "email": "admin_test@pharmacare.local",
        "full_name": "Dr. Test Admin",
        "role": "admin",
        "phone": "+91 98765 00001",
        "is_active": True,
    }


@pytest.fixture
def pharma_user_payload():
    """Return dictionary payload representing logged-in pharmacist."""
    return {
        "id": 2,
        "username": "pharma_test",
        "email": "pharma_test@pharmacare.local",
        "full_name": "Test Pharmacist",
        "role": "pharmacist",
        "phone": "+91 98765 00002",
        "is_active": True,
    }
