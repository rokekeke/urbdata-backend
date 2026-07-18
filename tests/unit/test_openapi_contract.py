"""OpenAPI contract guard (Fase 1, nota 28): the generated TypeScript
client depends on every operation having a typed success response and on
declared 4xx errors following the `{detail: {error, message, context}}`
envelope. No database involved - the spec is static."""

from typing import Any

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _operations(spec: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, operation)
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]


class TestOpenAPIContract:
    def setup_method(self) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        self.spec = response.json()

    def test_every_success_response_has_a_schema(self) -> None:
        untyped: list[str] = []
        for path, method, operation in _operations(self.spec):
            success = [
                body
                for status, body in operation["responses"].items()
                if status.startswith("2")
            ]
            for body in success:
                content = body.get("content", {})
                schema = content.get("application/json", {}).get("schema")
                if schema is None or schema == {}:
                    untyped.append(f"{method.upper()} {path}")
        assert not untyped, f"Operacoes sem schema de sucesso: {untyped}"

    def test_declared_client_errors_use_the_error_envelope(self) -> None:
        # FastAPI's request-validation 422 (HTTPValidationError) is the one
        # framework-shaped exception allowed in v1.
        missing: list[str] = []
        for path, method, operation in _operations(self.spec):
            for status, body in operation["responses"].items():
                if not status.startswith("4"):
                    continue
                schema = (
                    body.get("content", {}).get("application/json", {}).get("schema", {})
                )
                ref = schema.get("$ref", "")
                if ref.endswith("HTTPValidationError"):
                    continue
                if not ref.endswith("ErrorEnvelopeOut"):
                    missing.append(f"{method.upper()} {path} {status}")
        assert not missing, f"4xx fora do envelope de erro: {missing}"

    def test_error_envelope_shape(self) -> None:
        detail = self.spec["components"]["schemas"]["ErrorDetailOut"]
        assert set(detail["required"]) == {"error", "message", "context"}

    def test_key_routes_declare_their_error_responses(self) -> None:
        paths = self.spec["paths"]
        analyze = paths["/v1/projects/{project_id}/analyze"]["post"]["responses"]
        assert "404" in analyze and "422" in analyze
        upload = paths["/v1/projects/{project_id}/layers"]["post"]["responses"]
        assert {"400", "404", "413"} <= set(upload)
        geojson = paths["/v1/projects/{project_id}/layers/{layer_id}/geojson"]["get"]
        schema_ref = geojson["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema_ref["$ref"].endswith("GeoJSONFeatureCollectionOut")
