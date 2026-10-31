import pytest

from fintracker_internal_http.config import AWS_RUNTIME_MARKERS

USER_ID = "11111111-1111-4111-8111-111111111111"
CALLER = "arn:aws:sts::111111111111:assumed-role/test-caller/session"
ALLOWED_PREFIX = "arn:aws:sts::111111111111:assumed-role/test-caller"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with no internal-HTTP settings and no AWS runtime marker."""
    for name in (
        "INTERNAL_AUTH_MODE",
        "INTERNAL_ALLOWED_CALLER_ARNS",
        "INTERNAL_LOCAL_CALLER_ARN",
        "INTERNAL_BASE_URL_LEDGER",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        *AWS_RUNTIME_MARKERS,
    ):
        monkeypatch.delenv(name, raising=False)
