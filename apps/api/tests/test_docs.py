from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    ChatMessageCreateRequest,
    ChatRoomCreateRequest,
    MessageCreateRequest,
    MessageUpdateRequest,
    ProfileUpsertRequest,
    RecordPatchRequest,
)


def _openapi() -> dict:
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_scalar_docs_and_health_endpoints():
    with TestClient(app) as client:
        docs = client.get("/docs")
        assert docs.status_code == 200
        assert "/openapi.json" in docs.text

        preview = client.get("/vision-test")
        assert preview.status_code == 200
        assert preview.headers["cache-control"] == "no-store"
        assert 'id="overlay"' in preview.text

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}


def test_openapi_metadata_tags_and_security():
    spec = _openapi()

    multipart = spec["paths"]["/records/{record_id}/analyze"]["post"]["requestBody"]["content"]["multipart/form-data"]
    body_name = multipart["schema"]["$ref"].split("/")[-1]
    photos = spec["components"]["schemas"][body_name]["properties"]["photos"]
    assert photos["type"] == "array"
    assert photos["items"] == {"type": "string", "format": "binary"}

    assert spec["info"]["title"] == "Career Pair API"
    assert spec["info"]["version"] == "0.1.0"
    assert spec["info"]["description"].strip()

    tags = {tag["name"]: tag for tag in spec["tags"]}
    expected_tags = {
        "records", "diagnosis", "profile", "support-programs", "drafts", "providers", "chat", "health"
    }
    assert expected_tags <= set(tags)
    for name in expected_tags:
        assert tags[name]["description"].strip()

    bearer = spec["components"]["securitySchemes"]["HTTPBearer"]
    assert bearer["bearerFormat"] == "JWT"
    assert bearer["description"].strip()


def test_openapi_endpoints_have_descriptions_responses_and_params():
    spec = _openapi()
    expected_statuses = {
        ("/health", "get"): {"200"},
        ("/records", "post"): {"201", "401"},
        ("/records", "get"): {"200", "401"},
        ("/me/profile", "get"): {"200", "401", "404"},
        ("/me/profile", "put"): {"200", "401", "422"},
        ("/regions", "get"): {"200", "401"},
        ("/support-programs", "get"): {"200", "401", "404", "422"},
        ("/support-programs/{program_id}", "get"): {"200", "401", "404", "422"},
        ("/records/{record_id}", "get"): {"200", "401", "404", "422"},
        ("/records/{record_id}", "patch"): {"200", "401", "404", "422"},
        ("/records/{record_id}/messages", "post"): {"200", "401", "404", "409", "422"},
        ("/records/{record_id}/messages/{message_id}", "put"): {
            "200",
            "401",
            "404",
            "409",
            "422",
        },
        ("/records/{record_id}/next-question", "post"): {
            "200",
            "401",
            "404",
            "409",
            "422",
        },
        ("/records/{record_id}/analyze", "post"): {
            "200",
            "401",
            "404",
            "409",
            "422",
            "502",
            "503",
            "504",
        },
        ("/records/{record_id}/diagnosis", "post"): {
            "200",
            "401",
            "404",
            "409",
            "422",
            "502",
            "503",
            "504",
        },
        ("/records/{record_id}/drafts/{kind}", "post"): {
            "200",
            "401",
            "404",
            "409",
            "422",
            "502",
            "503",
            "504",
        },
        ("/records/{record_id}/drafts/{kind}/template", "get"): {
            "200",
            "401",
            "404",
            "422",
        },
        ("/work-types", "get"): {"200", "401"},
        ("/providers", "get"): {"200", "401", "422"},
        ("/providers/{provider_id}", "get"): {"200", "401", "404", "422"},
        ("/chat/rooms", "get"): {"200", "401"},
        ("/chat/rooms", "post"): {"200", "401", "404", "422"},
        ("/chat/rooms/{room_id}/read", "post"): {"200", "401", "404", "422"},
        ("/chat/rooms/{room_id}/messages", "get"): {"200", "401", "404", "422"},
        ("/chat/rooms/{room_id}/messages", "post"): {
            "200",
            "401",
            "404",
            "409",
            "422",
        },
    }

    actual_operations = set()
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            actual_operations.add((path, method))
            assert operation.get("summary", "").strip(), f"{method} {path} missing summary"
            assert operation.get("description", "").strip(), (
                f"{method} {path} missing description"
            )

            responses = operation["responses"]
            assert set(responses) == expected_statuses[(path, method)]

            for param in operation.get("parameters", []):
                if param.get("in") == "path":
                    assert param.get("description", "").strip(), (
                        f"{method} {path} param {param['name']} missing description"
                    )

            if "422" in responses:
                assert (
                    responses["422"]["content"]["application/json"]["schema"]["$ref"]
                    == "#/components/schemas/ErrorResponse"
                )
            if "409" in responses:
                # Record endpoints carry input_revision; chat conflicts do not.
                assert responses["409"]["content"]["application/json"]["schema"]["$ref"] in {
                    "#/components/schemas/ConflictErrorResponse",
                    "#/components/schemas/ErrorResponse",
                }

    assert actual_operations == set(expected_statuses)


def test_openapi_request_examples_validate_and_schemas_are_documented():
    spec = _openapi()
    schemas = spec["components"]["schemas"]

    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas

    for schema_name, schema in schemas.items():
        assert schema.get("description", "").strip(), (
            f"schema {schema_name} missing description"
        )
        for prop_name, prop_schema in schema.get("properties", {}).items():
            assert prop_schema.get("description", "").strip(), (
                f"schema {schema_name}.{prop_name} missing description"
            )

    request_models = {
        ("/records/{record_id}", "patch"): RecordPatchRequest,
        ("/records/{record_id}/messages", "post"): MessageCreateRequest,
        ("/records/{record_id}/messages/{message_id}", "put"): MessageUpdateRequest,
        ("/me/profile", "put"): ProfileUpsertRequest,
        ("/chat/rooms", "post"): ChatRoomCreateRequest,
        ("/chat/rooms/{room_id}/messages", "post"): ChatMessageCreateRequest,
    }
    for (path, method), model in request_models.items():
        examples = spec["paths"][path][method]["requestBody"]["content"][
            "application/json"
        ]["examples"]
        assert examples, f"{method} {path} missing requestBody examples"
        for example_name, example in examples.items():
            assert "value" in example, f"{method} {path} example {example_name} missing value"
            model.model_validate(example["value"])
