"""Category service for classification and catalog organization."""

from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.exceptions import (
    ValidationError,
    NotFoundException,
    ConflictException,
)
from app.models.category import Category
from app.models.medicine import Medicine
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class CategoryService:
    """Business logic and operations for pharmaceutical categories."""

    @staticmethod
    def list_categories() -> List[Dict[str, Any]]:
        """List all categories with count of assigned medicines."""
        with get_db() as session:
            stmt = (
                select(
                    Category,
                    func.count(Medicine.id).label("medicine_count")
                )
                .outerjoin(Medicine, Category.id == Medicine.category_id)
                .group_by(Category.id)
                .order_by(Category.name.asc())
            )
            rows = session.execute(stmt).all()

            categories = []
            for cat, count in rows:
                categories.append({
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description or "",
                    "medicine_count": count,
                    "created_at": cat.created_at.strftime("%Y-%m-%d") if cat.created_at else "",
                })
            return categories

    @staticmethod
    def get_category(category_id: int) -> Dict[str, Any]:
        """Fetch category by ID."""
        with get_db() as session:
            cat = session.get(Category, category_id)
            if not cat:
                raise NotFoundException(f"Category with ID {category_id} not found.")
            return {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description or "",
            }

    @staticmethod
    def create_category(current_user: Dict[str, Any], name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a new medicine category."""
        name = (name or "").strip()
        if not name:
            raise ValidationError("Category name is required.")

        with get_db() as session:
            existing = session.scalars(
                select(Category).where(func.lower(Category.name) == name.lower())
            ).first()
            if existing:
                raise ConflictException(f"A category with name '{name}' already exists.")

            cat = Category(name=name, description=(description or "").strip())
            session.add(cat)
            session.flush()
            cat_id = cat.id

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="CREATE",
            module="CATEGORY",
            description=f"Created category '{name}'",
        )

        return {"id": cat_id, "name": name, "description": description}

    @staticmethod
    def update_category(
        current_user: Dict[str, Any],
        category_id: int,
        name: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update existing category details."""
        name = (name or "").strip()
        if not name:
            raise ValidationError("Category name is required.")

        with get_db() as session:
            cat = session.get(Category, category_id)
            if not cat:
                raise NotFoundException(f"Category with ID {category_id} not found.")

            # Check if name changed and conflicts with another category
            if cat.name.lower() != name.lower():
                existing = session.scalars(
                    select(Category).where(
                        (func.lower(Category.name) == name.lower()) & (Category.id != category_id)
                    )
                ).first()
                if existing:
                    raise ConflictException(f"Category '{name}' already exists.")

            old_name = cat.name
            cat.name = name
            cat.description = (description or "").strip()

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="UPDATE",
            module="CATEGORY",
            description=f"Updated category '{old_name}' -> '{name}'",
        )

        return {"id": category_id, "name": name, "description": description}

    @staticmethod
    def delete_category(current_user: Dict[str, Any], category_id: int) -> None:
        """Delete category if no medicines are associated with it."""
        with get_db() as session:
            cat = session.get(Category, category_id)
            if not cat:
                raise NotFoundException(f"Category with ID {category_id} not found.")

            # Rule 7: Categories in use cannot be deleted
            med_count = session.scalars(
                select(func.count(Medicine.id)).where(Medicine.category_id == category_id)
            ).one()

            if med_count > 0:
                raise ConflictException(
                    f"Cannot delete category '{cat.name}' because {med_count} medicine(s) are linked to it. Please reassign those medicines first."
                )

            cat_name = cat.name
            session.delete(cat)

        AuditService.log_action(
            user_id=current_user.get("id"),
            username=current_user.get("username", "system"),
            action="DELETE",
            module="CATEGORY",
            description=f"Deleted category '{cat_name}'",
        )
