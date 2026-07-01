"""Contract tests for OpenAPI specification validation."""

from unittest.mock import MagicMock, patch

import anyio
import httpx
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, Phase, settings
from openapi_spec_validator import validate
from schemathesis.specs.openapi.checks import (
    ignored_auth,
    negative_data_rejection,
    positive_data_acceptance,
    unsupported_method,
)
from sqlmodel import Session, SQLModel, create_engine, delete
from sqlmodel.pool import StaticPool

from app import APP_VERSION
from app.db import get_async_session
from app.main import app
from app.models import Panel, Status, Study

# ---------------------------------------------------------------------------
# Schema-structure tests (what endpoints / schemas SHOULD exist in the spec)
# ---------------------------------------------------------------------------


class TestOpenAPISpec:
    """Tests for OpenAPI specification validation."""

    def test_openapi_schema_is_valid(self, client: TestClient):
        """Test that the generated OpenAPI schema is valid."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_spec = response.json()

        # Validate the OpenAPI spec itself
        validate(openapi_spec)

    def test_openapi_has_required_info(self, client: TestClient):
        """Test that OpenAPI spec has required information."""
        response = client.get("/openapi.json")
        spec = response.json()

        assert "openapi" in spec
        assert spec["openapi"].startswith("3.")
        assert "info" in spec
        assert spec["info"]["title"] == "cBioPortal Ingest API"
        assert spec["info"]["version"] == APP_VERSION
        assert spec["info"]["description"] == "REST API for ingesting data into cBioPortal"

    def test_openapi_has_all_endpoints(self, client: TestClient):
        """Test that all expected endpoints are documented."""
        response = client.get("/openapi.json")
        spec = response.json()

        paths = spec.get("paths", {})

        expected_paths = [
            "/",
            "/studies/",
            "/studies/{study_id}",
            "/validations/",
            "/validations/{validation_id}",
            "/panels/",
            "/panels/{panel_id}",
        ]

        for path in expected_paths:
            assert path in paths, f"Path {path} not found in OpenAPI spec"

    def test_openapi_endpoints_have_security(self, client: TestClient):
        """Test that protected endpoints have security requirements."""
        response = client.get("/openapi.json")
        spec = response.json()

        paths = spec.get("paths", {})

        protected_paths = [
            ("/studies/", "get"),
            ("/studies/", "post"),
            ("/studies/{study_id}", "delete"),
            ("/validations/", "get"),
            ("/validations/", "post"),
            ("/validations/{validation_id}", "get"),
            ("/validations/{validation_id}", "delete"),
            ("/panels/", "get"),
            ("/panels/", "post"),
            ("/panels/{panel_id}", "delete"),
        ]

        for path, method in protected_paths:
            endpoint = paths.get(path, {}).get(method, {})
            assert "security" in endpoint, f"{method.upper()} {path} should have security"

    def test_openapi_has_schemas(self, client: TestClient):
        """Test that OpenAPI spec includes all model schemas."""
        response = client.get("/openapi.json")
        spec = response.json()

        schemas = spec.get("components", {}).get("schemas", {})

        expected_schemas = ["StudyResponse", "PanelResponse", "TaskInput", "ValidationResponse"]

        for schema_name in expected_schemas:
            assert schema_name in schemas, f"Schema {schema_name} not found in OpenAPI spec"

    def test_openapi_study_schema_structure(self, client: TestClient):
        """Test that Study schema has correct structure."""
        response = client.get("/openapi.json")
        spec = response.json()

        study_schema = spec["components"]["schemas"]["StudyResponse"]

        assert "properties" in study_schema
        props = study_schema["properties"]

        expected_fields = [
            "name",
            "status",
            "date",
            "logs",
            "job_id",
            "command",
            "cbioportal_version",
            "id",
            "in_source_folder",
        ]

        for field in expected_fields:
            assert field in props, f"Field {field} not in Study schema"

    def test_openapi_panel_schema_structure(self, client: TestClient):
        """Test that Panel schema has correct structure."""
        response = client.get("/openapi.json")
        spec = response.json()

        panel_schema = spec["components"]["schemas"]["PanelResponse"]

        assert "properties" in panel_schema
        props = panel_schema["properties"]

        expected_fields = [
            "name",
            "status",
            "date",
            "logs",
            "job_id",
            "command",
            "cbioportal_version",
            "id",
            "in_source_folder",
        ]

        for field in expected_fields:
            assert field in props, f"Field {field} not in Panel schema"

    def test_openapi_validation_schema_structure(self, client: TestClient):
        """Test that ValidationResponse schema has correct structure."""
        response = client.get("/openapi.json")
        spec = response.json()

        validation_schema = spec["components"]["schemas"]["ValidationResponse"]

        assert "properties" in validation_schema
        props = validation_schema["properties"]

        expected_fields = [
            "name",
            "status",
            "date",
            "logs",
            "job_id",
            "command",
            "cbioportal_version",
            "id",
            "study_id",
        ]

        for field in expected_fields:
            assert field in props, f"Field {field} not in ValidationResponse schema"

    def test_status_enum_schema_matches_model(self, client: TestClient):
        """Test that Status enum in schema matches the actual Status enum."""
        response = client.get("/openapi.json")
        spec = response.json()

        status_schema = spec["components"]["schemas"]["Status"]

        assert "enum" in status_schema
        schema_values = set(status_schema["enum"])
        actual_values = {s.value for s in Status}

        assert schema_values == actual_values, (
            f"Schema enum {schema_values} doesn't match model {actual_values}"
        )

    def test_no_deprecated_endpoints(self, client: TestClient):
        """Test that no endpoints are marked as deprecated."""
        response = client.get("/openapi.json")
        spec = response.json()

        for path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                if isinstance(details, dict):
                    assert not details.get("deprecated", False), (
                        f"{method.upper()} {path} is marked as deprecated"
                    )


# ---------------------------------------------------------------------------
# Schemathesis contract tests (property-based, auto-generated by Hypothesis)
# ---------------------------------------------------------------------------

# Load the generated OpenAPI spec without starting the ASGI lifespan.
schemathesis_schema = schemathesis.openapi.from_dict(app.openapi())

# Module-level engine: created once, shared across all Hypothesis iterations.
_conformance_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_conformance_engine)


@schemathesis_schema.parametrize()
@settings(max_examples=5, phases=[Phase.generate], suppress_health_check=[HealthCheck.too_slow])
def test_api_conformance(case):
    """Property-based contract test: every auto-generated request must receive
    a response that conforms to the OpenAPI spec.

    Schemathesis drives Hypothesis to produce valid inputs, edge cases, and
    boundary values for every endpoint automatically.
    """
    mock_job = MagicMock()
    mock_job.id = "test-job-id"

    with Session(_conformance_engine) as session:
        # Keep each generated example independent and avoid stateful side effects
        # between POST calls that may intentionally trigger business-rule 400s.
        session.exec(delete(Study))
        session.exec(delete(Panel))
        session.commit()

        async def get_session_override():
            return session

        app.dependency_overrides[get_async_session] = get_session_override
        with patch("app.db.engine", _conformance_engine):
            try:
                with (
                    patch("app.routers.studies.queue") as sq,
                    patch("app.routers.panels.queue") as pq,
                    patch("app.routers.validations.queue") as vq,
                ):
                    sq.enqueue.return_value = mock_job
                    pq.enqueue.return_value = mock_job
                    vq.enqueue.return_value = mock_job
                    request_kwargs = case.as_transport_kwargs(
                        base_url="http://testserver",
                        headers={"Authorization": "Bearer test-token"},
                    )

                    request_kwargs["headers"].pop("Authorization", None)
                    request_kwargs["headers"]["Authorization"] = "Bearer test-token"

                    # httpx deprecation: prefer `content=` for raw bytes/text bodies.
                    # Schemathesis may return `data` as raw bytes/str; normalize it to
                    # `content` to avoid DeprecationWarning from httpx internals.
                    if "data" in request_kwargs and isinstance(
                        request_kwargs["data"], (bytes, str)
                    ):
                        request_kwargs["content"] = request_kwargs.pop("data")
                    # Normalize all headers: encode any non-ASCII str keys/values to UTF-8
                    headers = request_kwargs.get("headers")
                    if headers:
                        normalized = {}
                        # support both dict and list-of-tuples
                        items = headers.items() if hasattr(headers, "items") else headers
                        for hk, hv in items:
                            new_k = hk
                            new_v = hv
                            if isinstance(hk, str):
                                try:
                                    hk.encode("ascii")
                                except UnicodeEncodeError:
                                    new_k = hk.encode("utf-8")
                            if isinstance(hv, str):
                                try:
                                    hv.encode("ascii")
                                except UnicodeEncodeError:
                                    new_v = hv.encode("utf-8")
                            normalized[new_k] = new_v
                        request_kwargs["headers"] = normalized

                    cookies = request_kwargs.pop("cookies", None)

                    async def call_api():
                        transport = httpx.ASGITransport(app=app)
                        async with httpx.AsyncClient(
                            transport=transport,
                            base_url="http://testserver",
                            cookies=cookies,
                        ) as api_client:
                            return await api_client.request(**request_kwargs)

                    response = anyio.run(call_api)
                case.validate_response(
                    response,
                    excluded_checks=[
                        ignored_auth,
                        negative_data_rejection,
                        positive_data_acceptance,
                        unsupported_method,
                    ],
                )
            finally:
                app.dependency_overrides.pop(get_async_session, None)
