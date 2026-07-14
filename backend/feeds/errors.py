"""Feed-layer errors surfaced to scheduler job status (ERR-001)."""


class FeedFetchError(Exception):
    """Critical upstream feed fetch failed (not a legitimate empty catalog)."""
