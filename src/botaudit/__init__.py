"""BotAudit — AI accessibility auditing for web pages.

SPEC-library-mode FR-3: Public API exports.
NFR-3.1: No I/O, network, or filesystem access on import.
NFR-3.2: No stdout/stderr output on import.
"""

from botaudit.api import audit, audit_batch
from botaudit.batch import BatchResult, URLError, URLSuccess
from botaudit.fetcher import FetchError
from botaudit.models import (
    CATEGORY_WEIGHTS,
    WEIGHT_PROFILES,
    CategoryResult,
    Recommendation,
    Report,
    Severity,
    resolve_weights,
)
from botaudit.page_type import PageTypeResult, PageTypeSignal

__version__ = "0.1.0"

__all__ = [
    # Functions
    "audit",
    "audit_batch",
    "resolve_weights",
    # Data classes
    "Report",
    "CategoryResult",
    "Recommendation",
    "BatchResult",
    "URLSuccess",
    "URLError",
    "PageTypeResult",
    "PageTypeSignal",
    # Enums
    "Severity",
    # Exceptions
    "FetchError",
    # Constants
    "CATEGORY_WEIGHTS",
    "WEIGHT_PROFILES",
    "__version__",
]
