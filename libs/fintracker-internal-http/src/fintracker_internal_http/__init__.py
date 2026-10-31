"""fintracker-internal-http: one way to send and receive internal calls between FinTracker Python services (LB-IHTTP).

The public API is exactly `__all__` (LB-PKG-02). `fintracker_internal_http.testing` is a separate module for
tests and is never imported from here.

__author__ = "Van Vo"
"""
from importlib.metadata import PackageNotFoundError, version

from .config import AuthMode, InternalConfigError, InternalSettings, base_url_for, load_settings
from .context import InvalidUserContextError, UserContext, set_current_traceparent
from .inbound import (
    InternalRejection,
    caller_rejection,
    get_internal_user,
    install_internal_exception_handlers,
    internal_rejection_handler,
    require_internal_caller,
    user_context_from_headers,
)
from .outbound import HeaderSigner, InternalCallError, InternalClient, InternalResponse, SigningError, SigV4Signer

try:
    __version__ = version("fintracker-internal-http")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

__all__ = [
    "AuthMode",
    "HeaderSigner",
    "InternalCallError",
    "InternalClient",
    "InternalConfigError",
    "InternalRejection",
    "InternalResponse",
    "InternalSettings",
    "InvalidUserContextError",
    "SigV4Signer",
    "SigningError",
    "UserContext",
    "__version__",
    "base_url_for",
    "caller_rejection",
    "get_internal_user",
    "install_internal_exception_handlers",
    "internal_rejection_handler",
    "load_settings",
    "require_internal_caller",
    "set_current_traceparent",
    "user_context_from_headers",
]
