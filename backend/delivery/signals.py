"""Register delivery and dispatch receivers after Django loads its models."""
from . import user_signals  # noqa: F401
from dispatch import events  # noqa: F401
