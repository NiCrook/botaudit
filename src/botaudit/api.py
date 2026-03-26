"""Public API entry points for botaudit (SPEC-library-mode).

FR-4.1: audit() and audit_batch() live here.
FR-4.2: Thin wrappers over existing internal modules.
FR-4.3: No CLI or argparse imports.
"""

from __future__ import annotations

from botaudit.batch import (
    BatchResult,
    URLError,
    URLSuccess,
    audit_one,
)
from botaudit.fetcher import FetchError
from botaudit.models import Report


def audit(
    url: str,
    *,
    timeout: float = 10.0,
    skip_llm_discovery: bool = False,
    no_recommendations: bool = False,
    weights: dict[str, float] | None = None,
    page_type_mode: str = "auto",
) -> Report:
    """Run a full audit on a single URL and return the report.

    FR-1.1: Signature matches spec.
    FR-1.2: Delegates to the existing pipeline via batch.audit_one().
    FR-1.3: Raises FetchError on failure instead of returning URLError.
    FR-1.5: No stdout/stderr output.
    FR-1.6: Never calls sys.exit().
    """
    result = audit_one(
        url,
        timeout=timeout,
        skip_llm_discovery=skip_llm_discovery,
        no_recommendations=no_recommendations,
        weights=weights,
        page_type_mode=page_type_mode,
    )

    if isinstance(result, URLError):
        raise FetchError(result.message)

    return result.report


def audit_batch(
    urls: list[str],
    *,
    timeout: float = 10.0,
    skip_llm_discovery: bool = False,
    no_recommendations: bool = False,
    weights: dict[str, float] | None = None,
    page_type_mode: str = "auto",
) -> BatchResult:
    """Run a full audit on multiple URLs and return aggregate results.

    FR-2.1: Signature matches spec.
    FR-2.2: Delegates to batch.run_batch() with quiet=True.
    FR-2.3: No progress messages (quiet=True).
    FR-2.4: Raises ValueError on empty list, never calls sys.exit().
    """
    if not urls:
        raise ValueError("urls must not be empty")

    from botaudit.batch import run_batch

    return run_batch(
        urls,
        timeout=timeout,
        skip_llm_discovery=skip_llm_discovery,
        no_recommendations=no_recommendations,
        quiet=True,
        weights=weights,
        page_type_mode=page_type_mode,
    )
