from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import (
    DEFAULT_POLICY_STRICT_STALE_AGE_DAYS,
    DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS,
    DEFAULT_POLICY_WARNING_AGE_DAYS,
    DEFAULT_POLICY_WARNING_AGE_SECONDS,
)


def parse_iso_utc_datetime(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def epoch_seconds_from_iso(value: str | None) -> int | None:
    parsed = parse_iso_utc_datetime(value)
    if parsed is None:
        return None
    return int(parsed.timestamp())


def epoch_milliseconds_from_iso(value: str | None) -> int | None:
    parsed = parse_iso_utc_datetime(value)
    if parsed is None:
        return None
    return int(parsed.timestamp()) * 1000 + parsed.microsecond // 1000


def freshness_policy_metadata() -> dict[str, Any]:
    return {
        "warning_after_days": DEFAULT_POLICY_WARNING_AGE_DAYS,
        "strict_stale_after_days": DEFAULT_POLICY_STRICT_STALE_AGE_DAYS,
        "max_ok_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "warning_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "strict_stale_age_seconds": DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS,
        "client_recomputes_age": True,
    }


def freshness_thresholds(generated_at_utc: str | None) -> dict[str, Any]:
    generated_epoch = epoch_seconds_from_iso(generated_at_utc)
    warn_after = None
    stale_after = None
    if generated_epoch is not None:
        warn_after = generated_epoch + DEFAULT_POLICY_WARNING_AGE_SECONDS
        stale_after = generated_epoch + DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS
    return {
        "generated_at_epoch_s": generated_epoch,
        "warn_after_epoch_s": warn_after,
        "stale_after_epoch_s": stale_after,
        "strict_stale_after_epoch_s": stale_after,
        "max_ok_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "warning_age_seconds": DEFAULT_POLICY_WARNING_AGE_SECONDS,
        "strict_stale_age_seconds": DEFAULT_POLICY_STRICT_STALE_AGE_SECONDS,
    }


__all__ = [
    "epoch_milliseconds_from_iso",
    "epoch_seconds_from_iso",
    "freshness_policy_metadata",
    "freshness_thresholds",
    "parse_iso_utc_datetime",
]
