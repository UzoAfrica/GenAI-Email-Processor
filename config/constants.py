from typing import Final

# API Constants
MAX_RETRIES: Final[int] = 3
RETRY_DELAY: Final[float] = 1.5  # seconds
REQUEST_TIMEOUT: Final[int] = 30  # seconds

# Data Processing
DEFAULT_BATCH_SIZE: Final[int] = 50
MAX_THREADS: Final[int] = 5

# Status Codes
STATUS_SUCCESS: Final[str] = "success"
STATUS_FAILED: Final[str] = "failed"
STATUS_PARTIAL: Final[str] = "partial"

# Email Classification
CLASSIFICATION_TYPES: Final[dict] = {
    "ORDER_REQUEST": "order request",
    "PRODUCT_INQUIRY": "product inquiry",
    "UNCLASSIFIED": "unclassified"
}

# Order Processing
ORDER_STATUSES: Final[dict] = {
    "FULFILLED": "fulfilled",
    "OUT_OF_STOCK": "out_of_stock",
    "INVALID": "invalid",
    "PENDING": "pending"
}

# Field Validation
REQUIRED_EMAIL_FIELDS: Final[list] = [
    "email_id",
    "subject",
    "message"
]

REQUIRED_ORDER_FIELDS: Final[list] = [
    "order_id",
    "product_id",
    "quantity"
]

# Date Formats
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_FILE: Final[str] = "%Y%m%d_%H%M%S"