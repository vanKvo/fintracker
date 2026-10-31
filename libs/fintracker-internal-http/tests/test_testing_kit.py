"""LB-IHTTP-08: the package ships fakes and a conformance suite."""
import json
import subprocess
import sys
from importlib import metadata

import pytest
from fastapi import Depends, FastAPI

import fintracker_internal_http
from fintracker_internal_http import UserContext, get_internal_user
from fintracker_internal_http.testing import load_vectors, run_conformance


def wired_app() -> FastAPI:
    app = FastAPI()

    @app.get("/internal/v1/things")
    async def things(user: UserContext = Depends(get_internal_user(require=("user", "timezone", "currency")))) -> dict[str, str]:  # type: ignore[arg-type]
        return {"ok": "yes"}

    return app


def route_without_caller_check() -> FastAPI:
    app = FastAPI()

    @app.get("/internal/v1/things")
    async def things() -> dict[str, str]:
        return {"ok": "yes"}

    return app


class TestTestingKit:
    def test_run_conformance_passes_for_a_route_wired_with_the_dependencies(self) -> None:
        """LB-IHTTP-08: happy path, and the vectors file is plain JSON at the library's own version."""
        run_conformance(wired_app, path="/internal/v1/things", requires=("user", "timezone", "currency"))
        vectors = load_vectors()
        assert vectors["library_version"] == metadata.version("fintracker-internal-http")
        assert {row["id"] for row in vectors["caller_matrix"]} >= {"iam-no-caller", "iam-off-list", "local-on-list"}
        json.dumps(vectors)  # plain data

    def test_run_conformance_fails_for_a_route_that_skips_the_caller_check(self) -> None:
        """LB-IHTTP-08: fails on the 401 case."""
        with pytest.raises(AssertionError, match="iam-no-caller"):
            run_conformance(route_without_caller_check, path="/internal/v1/things")

    def test_a_row_a_services_own_spec_answers_differently_is_named_and_checked_against_that_answer(self) -> None:
        """LB-IHTTP-08: `own_answers` replaces the expected (status, code) of a named row, never skips it."""
        # The route is right by the matrix, so a different expected answer for one row makes exactly that row fail.
        with pytest.raises(AssertionError, match="iam-user-missing: expected \\(400, 'invalid_argument'\\), got \\(401"):
            run_conformance(
                wired_app, path="/internal/v1/things", requires=("user", "timezone", "currency"),
                own_answers={"iam-user-missing": (400, "invalid_argument")},
            )
        with pytest.raises(ValueError, match="no-such-row"):
            run_conformance(wired_app, path="/internal/v1/things", own_answers={"no-such-row": (400, "x")})

    def test_importing_the_library_does_not_import_the_testing_module(self) -> None:
        """LB-IHTTP-08: not in production paths."""
        code = "import sys, fintracker_internal_http; sys.exit(1 if 'fintracker_internal_http.testing' in sys.modules else 0)"
        assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0
        assert fintracker_internal_http.__all__
