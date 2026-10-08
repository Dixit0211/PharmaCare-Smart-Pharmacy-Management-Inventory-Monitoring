"""Authentication and Role-Based Access Control (RBAC) service."""

from functools import wraps
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, hash_password
from app.core.exceptions import (
    AuthenticationError,
    ValidationError,
    NotFoundException,
    PermissionDeniedException,
    ConflictException,
)
from app.models.user import User
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


def require_role(*allowed_roles: str):
    """Decorator to enforce role permissions in domain services."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inspect args or kwargs for current_user dict or user role
            current_user = kwargs.get("current_user")
            if not current_user and len(args) > 0 and isinstance(args[0], dict) and "role" in args[0]:
                current_user = args[0]

            if not current_user:
                # Look for current_user inside any positional argument
                for arg in args:
                    if isinstance(arg, dict) and "role" in arg:
                        current_user = arg
                        break

            if not current_user:
                raise PermissionDeniedException("Authentication context missing: user must be logged in.")

            user_role = current_user.get("role", "").lower()
            allowed = [r.lower() for r in allowed_roles]

            if user_role not in allowed:
                raise PermissionDeniedException(
                    f"Access denied: role '{user_role}' is not authorized to perform this operation."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


class AuthService:
    """Manages authentication, password security, user lifecycle, and role verification."""

    @staticmethod
    def authenticate(identifier: str, password: str, ip_address: str = "127.0.0.1") -> Dict[str, Any]:
        """Authenticate user by email or username, returning safe user payload."""
        if not identifier or not password:
            raise ValidationError("Email/Username and password are required")

        identifier = identifier.strip().lower()

        with get_db() as session:
            stmt = select(User).where(
                (User.email.ilike(identifier)) | (User.username.ilike(identifier))
            )
            user = session.scalars(stmt).first()

            if not user:
                logger.warning(f"Failed login attempt for nonexistent user: {identifier}")
                raise AuthenticationError("Invalid email or password")

            if not user.is_active:
                logger.warning(f"Login attempt for deactivated user: {user.username}")
                raise AuthenticationError("This user account has been deactivated. Please contact the administrator.")

            if not verify_password(password, user.password_hash):
                logger.warning(f"Invalid password for user: {user.username}")
                raise AuthenticationError("Invalid email or password")

            user_payload = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "phone": user.phone,
                "is_active": user.is_active,
            }

        # Log successful login in audit trail
        AuditService.log_action(
            user_id=user_payload["id"],
            username=user_payload["username"],
            action="LOGIN",
            module="AUTH",
            description=f"User '{user_payload['username']}' logged in successfully",
            ip_address=ip_address,
        )

        return user_payload

    @staticmethod
    def change_password(user_id: int, old_password: str, new_password: str) -> None:
        """Allow an authenticated user to change their password securely."""
        if not old_password or not new_password:
            raise ValidationError("Old password and new password are required")

        if len(new_password) < 6:
            raise ValidationError("New password must be at least 6 characters long")

        with get_db() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundException("User not found")

            if not verify_password(old_password, user.password_hash):
                raise ValidationError("Current password is incorrect")

            user.password_hash = hash_password(new_password)
            username = user.username

        AuditService.log_action(
            user_id=user_id,
            username=username,
            action="CHANGE_PASSWORD",
            module="AUTH",
            description="User password changed successfully",
        )

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user by id."""
        with get_db() as session:
            user = session.get(User, user_id)
            if not user:
                return None
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }

    @staticmethod
    def list_users() -> List[Dict[str, Any]]:
        """List all registered users for administration."""
        with get_db() as session:
            stmt = select(User).order_by(User.role.asc(), User.username.asc())
            users = session.scalars(stmt).all()
            return [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "phone": u.phone or "",
                    "is_active": u.is_active,
                    "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
                }
                for u in users
            ]

    @staticmethod
    @require_role("admin")
    def create_user(
        current_user: Dict[str, Any],
        username: str,
        email: str,
        password: str,
        full_name: str,
        role: str = "pharmacist",
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Admin creation of a new staff account."""
        username = (username or "").strip()
        email = (email or "").strip().lower()
        full_name = (full_name or "").strip()

        if not username or not email or not password or not full_name:
            raise ValidationError("All required fields must be filled")

        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters")

        if role not in ["admin", "pharmacist"]:
            raise ValidationError("Role must be 'admin' or 'pharmacist'")

        with get_db() as session:
            # Check unique username and email
            existing = session.scalars(
                select(User).where((User.username == username) | (User.email == email))
            ).first()
            if existing:
                if existing.username.lower() == username.lower():
                    raise ConflictException(f"Username '{username}' is already taken.")
                raise ConflictException(f"Email '{email}' is already registered.")

            new_user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=role,
                phone=phone,
                is_active=True,
            )
            session.add(new_user)
            session.flush()
            new_id = new_user.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "admin"),
            action="CREATE",
            module="USERS",
            description=f"Created user '{username}' with role '{role}'",
        )

        return {"id": new_id, "username": username, "email": email, "role": role}

    @staticmethod
    @require_role("admin")
    def toggle_user_status(current_user: Dict[str, Any], user_id: int) -> bool:
        """Toggle active/inactive status of a user (cannot deactivate self)."""
        if current_user.get("id") == user_id:
            raise ValidationError("You cannot deactivate your own administrative account.")

        with get_db() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundException("User not found")

            user.is_active = not user.is_active
            new_status = user.is_active
            username = user.username

        action_desc = "activated" if new_status else "deactivated"
        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "admin"),
            action="UPDATE",
            module="USERS",
            description=f"User '{username}' {action_desc}",
        )
        return new_status

    @staticmethod
    @require_role("admin")
    def admin_reset_password(current_user: Dict[str, Any], user_id: int, new_password: str) -> None:
        """Admin override to reset a staff user's password."""
        if not new_password or len(new_password) < 6:
            raise ValidationError("Password must be at least 6 characters.")

        with get_db() as session:
            user = session.get(User, user_id)
            if not user:
                raise NotFoundException("User not found")

            user.password_hash = hash_password(new_password)
            username = user.username

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "admin"),
            action="UPDATE",
            module="USERS",
            description=f"Administrator reset password for staff user '{username}'",
        )

