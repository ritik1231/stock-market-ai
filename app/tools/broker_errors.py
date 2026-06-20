"""Shared broker error types — imported by all broker clients and consumers."""


class BrokerAPIError(Exception):
    pass


class BrokerServerError(BrokerAPIError):
    """Transient server errors — safe to retry."""
