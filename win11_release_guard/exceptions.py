class WindowsReleaseCheckerError(Exception):
    """Base exception for this package."""


class UnsupportedPlatformError(WindowsReleaseCheckerError):
    """Raised when a Windows-only probe is called on another platform."""


class PolicyError(WindowsReleaseCheckerError):
    """Raised when a release policy is missing or invalid."""


class PolicyParseError(PolicyError):
    """Raised when release policy source data cannot be parsed."""


class PolicyFetchError(PolicyError):
    """Raised when release policy source data cannot be fetched."""


class PolicyTrustError(PolicyError):
    """Raised when release policy signature or trust requirements fail."""


class LocalStateError(WindowsReleaseCheckerError):
    """Raised when local Windows state cannot be collected or interpreted."""
