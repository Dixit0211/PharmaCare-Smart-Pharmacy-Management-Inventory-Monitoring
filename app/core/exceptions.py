"""Domain exceptions for PharmaCare layered architecture."""


class AppException(Exception):
    """Base exception for all domain and service level errors."""

    def __init__(self, message: str, code: str = "APP_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

    def __str__(self) -> str:
        return self.message


class ValidationError(AppException):
    """Raised when user input or entity attributes fail business validation rules."""

    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


class NotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Requested item was not found"):
        super().__init__(message, code="NOT_FOUND")


class ConflictException(AppException):
    """Raised when an action conflicts with existing state (e.g., deleting a category in use)."""

    def __init__(self, message: str):
        super().__init__(message, code="CONFLICT")


class PermissionDeniedException(AppException):
    """Raised when a user attempts an unauthorized action for their role."""

    def __init__(self, message: str = "Access denied: insufficient permissions"):
        super().__init__(message, code="PERMISSION_DENIED")


class AuthenticationError(AppException):
    """Raised for invalid login credentials or expired session."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message, code="AUTHENTICATION_FAILED")


class InsufficientStockError(ValidationError):
    """Raised when stock is not sufficient for a requested sale quantity."""

    def __init__(self, message: str = "Insufficient stock available for requested medicine"):
        super().__init__(message)
        self.code = "INSUFFICIENT_STOCK"


class ExpiredBatchError(ValidationError):
    """Raised when trying to dispense or operate on an expired batch."""

    def __init__(self, message: str = "Expired medicine batch cannot be sold or dispensed"):
        super().__init__(message)
        self.code = "EXPIRED_BATCH"
