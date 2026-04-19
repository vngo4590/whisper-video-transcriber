"""Shared exception types for all controllers."""


class OperationCancelledError(Exception):
    """Raised inside a worker thread when the user clicks Cancel."""
