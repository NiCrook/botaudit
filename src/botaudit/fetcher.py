"""HTTP fetching for botaudit (Spec §2).

Performs a raw HTTP GET — no JavaScript execution — and returns the
response body as a string, or raises FetchError on any failure.
"""

import httpx

USER_AGENT = "botaudit/0.1.0 (+https://github.com/botaudit)"
DEFAULT_TIMEOUT = 10.0
MAX_REDIRECTS = 10


class FetchError(Exception):
    """Raised when a fetch fails for any reason (network, HTTP, timeout)."""


def fetch(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Fetch *url* via HTTP GET and return the response body text.

    Raises FetchError with a human-readable message on:
      - network errors (DNS failure, connection refused, etc.)
      - timeouts
      - HTTP error responses (4xx / 5xx)
    """
    try:
        with httpx.Client(
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(url)
    except httpx.TimeoutException:
        raise FetchError(f"Request timed out after {timeout}s: {url}")
    except httpx.TooManyRedirects:
        raise FetchError(
            f"Too many redirects (>{MAX_REDIRECTS}): {url}"
        )
    except httpx.ConnectError as exc:
        raise FetchError(f"Connection failed: {exc}")
    except httpx.HTTPError as exc:
        raise FetchError(f"Network error: {exc}")

    if response.status_code >= 400:
        raise FetchError(
            f"HTTP {response.status_code} {response.reason_phrase}: {url}"
        )

    return response.text
