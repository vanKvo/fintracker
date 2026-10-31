"""LB-IHTTP-01 / LB-IHTTP-02: settings and the local-in-AWS guard."""
import pytest

from fintracker_internal_http import AuthMode, InternalClient, InternalConfigError, load_settings
from fintracker_internal_http.config import AWS_RUNTIME_MARKERS


class TestSettings:
    def test_unset_mode_is_iam(self) -> None:
        """LB-IHTTP-01: strict is the default."""
        assert load_settings({}).mode is AuthMode.IAM

    def test_local_mode(self) -> None:
        """LB-IHTTP-01: INTERNAL_AUTH_MODE=local gives mode local."""
        assert load_settings({"INTERNAL_AUTH_MODE": "local"}).mode is AuthMode.LOCAL

    @pytest.mark.parametrize("value", ["Local", "LOCAL", "IAM", "", "   "])
    def test_wrong_case_or_empty_mode_is_invalid(self, value: str) -> None:
        """LB-IHTTP-01: case-sensitive, and a set-but-empty value never falls back to local."""
        with pytest.raises(InternalConfigError):
            load_settings({"INTERNAL_AUTH_MODE": value})

    def test_surrounding_spaces_are_trimmed(self) -> None:
        """LB-IHTTP-01: mode names are trimmed of spaces."""
        assert load_settings({"INTERNAL_AUTH_MODE": " local "}).mode is AuthMode.LOCAL

    def test_invalid_mode_names_the_variable_and_allowed_values_not_the_value(self) -> None:
        """LB-IHTTP-01: startup failure that names INTERNAL_AUTH_MODE and iam/local."""
        with pytest.raises(InternalConfigError) as error:
            load_settings({"INTERNAL_AUTH_MODE": "off-secret-value"})
        message = str(error.value)
        assert "INTERNAL_AUTH_MODE" in message and "iam" in message and "local" in message
        assert "off-secret-value" not in message

    def test_allowed_caller_arns_are_trimmed_deduplicated_and_empties_dropped(self) -> None:
        """LB-IHTTP-01: list parsing."""
        settings = load_settings({"INTERNAL_ALLOWED_CALLER_ARNS": " arn:a , ,arn:b,arn:a,"})
        assert settings.allowed_caller_arns == ("arn:a", "arn:b")

    @pytest.mark.parametrize("environ", [{}, {"INTERNAL_ALLOWED_CALLER_ARNS": ""}, {"INTERNAL_ALLOWED_CALLER_ARNS": " , "}])
    def test_empty_or_unset_list_is_valid(self, environ: dict[str, str]) -> None:
        """LB-IHTTP-01: an empty list is valid (every internal call is then a 403)."""
        assert load_settings(environ).allowed_caller_arns == ()

    def test_missing_base_url_raises_when_the_client_is_built_naming_the_variable(self) -> None:
        """LB-IHTTP-01: missing INTERNAL_BASE_URL_<SERVICE>."""
        with pytest.raises(InternalConfigError, match="INTERNAL_BASE_URL_LEDGER"):
            InternalClient.from_env("LEDGER", environ={})


class TestLocalGuard:
    def test_local_starts_without_markers(self) -> None:
        """LB-IHTTP-02: happy path."""
        assert load_settings({"INTERNAL_AUTH_MODE": "local"}).is_local

    @pytest.mark.parametrize("mode", [{}, {"INTERNAL_AUTH_MODE": "iam"}])
    def test_iam_starts_with_or_without_markers(self, mode: dict[str, str]) -> None:
        """LB-IHTTP-02: iam unaffected."""
        for marker in (None, *AWS_RUNTIME_MARKERS):
            environ = dict(mode) | ({marker: "x"} if marker else {})
            assert not load_settings(environ).is_local

    @pytest.mark.parametrize("marker", AWS_RUNTIME_MARKERS)
    def test_local_with_an_aws_marker_raises_naming_the_marker_not_its_value(self, marker: str) -> None:
        """LB-IHTTP-02: markers AWS_EXECUTION_ENV, AWS_LAMBDA_FUNCTION_NAME, ECS_CONTAINER_METADATA_URI(_V4)."""
        with pytest.raises(InternalConfigError) as error:
            load_settings({"INTERNAL_AUTH_MODE": "local", marker: "secret-runtime-value"})
        assert marker in str(error.value)
        assert "secret-runtime-value" not in str(error.value)
