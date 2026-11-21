from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from PIL import Image

from app import diagnosis, llm
from app.vision import normalize_label
from conftest import PNG_1X1


@pytest.fixture
def llm_settings(monkeypatch):
    monkeypatch.setattr(
        "app.diagnosis.get_settings",
        lambda: SimpleNamespace(llm_api_key="test-key"),
    )


def _work_types():
    return [
        {"work_type_id": uuid4(), "name": "곰팡이 제거"},
        {"work_type_id": uuid4(), "name": "원인 점검"},
    ]


def _payload(**overrides):
    payload = {
        "observations": "창틀 아래 검은 얼룩이 보입니다.",
        "suspected_types": ["곰팡이"],
        "severity_score": 55,
        "reason": "표면 곰팡이 가능성이 있습니다.",
        "causes": ["결로 가능성"],
        "recommended_action": "inspection",
        "care_steps": ["환기"],
        "supplies": ["마스크"],
        "prevention_tips": ["환기 유지"],
        "unknowns": ["누수 여부"],
        "work_type_id": None,
        "work_type_name": "곰팡이 제거",
        "work_type_reason": "곰팡이 제거가 필요해 보입니다.",
    }
    payload.update(overrides)
    return payload


def _normalize(payload, work_types, *, photo_analysis=None, symptoms=None):
    return diagnosis.normalize_diagnosis(
        payload,
        work_types=work_types,
        photo_analysis=photo_analysis,
        symptoms=symptoms,
    )


@pytest.mark.parametrize(
    "score,level", [(0, "low"), (39, "low"), (40, "medium"), (69, "medium"), (70, "high"), (100, "high")]
)
def test_severity_level_is_normalized_server_side(score, level):
    work_types = _work_types()
    result = _normalize(
        _payload(severity_score=score, work_type_name="곰팡이 제거"),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "곰팡이"}]}]},
    )
    assert result["severity_score"] == score
    assert result["severity_level"] == level


def test_no_evidence_forces_undetermined_and_inspection_work_type():
    work_types = _work_types()
    inspection_id = work_types[1]["work_type_id"]
    result = _normalize(
        _payload(
            severity_score=88,
            recommended_action="self_care",
            suspected_types=["곰팡이"],
        ),
        work_types,
        photo_analysis={"photos": [{"detections": []}]},
        symptoms="",
    )
    assert result["severity_score"] is None
    assert result["severity_level"] == "undetermined"
    assert result["suspected_types"] == []
    assert result["recommended_action"] == "inspection"
    assert UUID(result["work_type_id"]) == inspection_id


def test_null_severity_is_undetermined_even_with_evidence():
    work_types = _work_types()
    result = _normalize(
        _payload(severity_score=None, recommended_action="provider_consult"),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "균열"}]}]},
    )
    assert result["severity_score"] is None
    assert result["severity_level"] == "undetermined"
    assert result["recommended_action"] == "provider_consult"
    assert UUID(result["work_type_id"]) == work_types[1]["work_type_id"]


def test_official_type_terms_and_aliases_are_normalized():
    work_types = _work_types()
    result = _normalize(
        _payload(suspected_types=["크랙", "박리", "표면 이상"]),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "균열"}]}]},
    )
    assert result["suspected_types"] == ["균열", "벗겨짐"]
    assert normalize_label("mould") == "곰팡이"


def test_matching_work_type_name_is_kept():
    work_types = _work_types()
    result = _normalize(
        _payload(suspected_types=["곰팡이"], work_type_name="곰팡이 제거"),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "곰팡이"}]}]},
    )
    assert UUID(result["work_type_id"]) == work_types[0]["work_type_id"]


def test_unmatched_or_complex_work_type_falls_back_to_inspection():
    work_types = _work_types()
    inspection_id = work_types[1]["work_type_id"]

    unmatched = _normalize(
        _payload(work_type_name="없는 작업", work_type_id=str(uuid4())),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "곰팡이"}]}]},
    )
    assert UUID(unmatched["work_type_id"]) == inspection_id

    complex_cause = _normalize(
        _payload(suspected_types=["곰팡이", "균열"]),
        work_types,
        photo_analysis={"photos": [{"detections": [{"label": "곰팡이"}]}]},
    )
    assert UUID(complex_cause["work_type_id"]) == inspection_id


@pytest.mark.parametrize("field", ["causes", "care_steps", "supplies", "prevention_tips", "unknowns"])
def test_missing_list_field_is_a_model_error(field):
    payload = _payload()
    payload[field] = "not-a-list"
    with pytest.raises(llm.LlmError):
        _normalize(payload, _work_types())


def test_prompt_uses_only_observations_and_masks_contact_details():
    work_types = [
        {"work_type_id": "11111111-1111-4111-8111-111111111111", "name": "곰팡이 제거"},
        {"work_type_id": "22222222-2222-4222-8222-222222222222", "name": "원인 점검"},
    ]
    record = {
        "location": "안방 창틀",
        "material": "실리콘",
        "symptoms": "010-1234-5678 test@example.com 으로 연락",
        "photo_observations": {
            "photos": [
                {
                    "role": "overview",
                    "status": "analyzed",
                    "source": "yolo",
                    "detections": [
                        {
                            "label": "곰팡이",
                            "raw_label": "mold",
                            "confidence": 0.87,
                            "area_ratio": 0.123,
                            "bbox": [911, 922, 933, 944],
                            "mask": {"counts": "SECRET-RLE", "svg_path": "SECRET-SVG"},
                        }
                    ],
                    "vision_observation": {
                        "suspected_types": ["곰팡이"],
                        "summary": "창틀 아래 검은 얼룩",
                        "approximate_location": "아래쪽",
                        "unreadable_reason": None,
                    },
                },
                {"role": "closeup", "status": "failed", "source": "vision_llm"},
            ]
        },
    }
    prompt = diagnosis.build_prompt(record, work_types)
    assert "곰팡이" in prompt
    assert "신뢰도 87%" in prompt
    assert "화면 점유 비율 12.3%" in prompt
    assert "실제 물리 면적이 아님" in prompt
    assert "곰팡이 제거" in prompt
    assert "원인 점검" in prompt
    assert "[개인정보 제거]" in prompt
    assert "test@example.com" not in prompt
    assert "010-1234-5678" not in prompt
    for forbidden in ("911", "922", "933", "944", "SECRET-RLE", "SECRET-SVG"):
        assert forbidden not in prompt


def test_diagnosis_endpoint_reuses_current_diagnosis_without_model(
    llm_settings, client, user_factory, token_for, analyzed_record_factory, monkeypatch
):
    user_id = user_factory()
    record_id = analyzed_record_factory(user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    def fail(*_a, **_k):
        raise AssertionError("model must not be called for a current diagnosis")

    monkeypatch.setattr("app.diagnosis.llm.generate_json", fail)
    response = client.post(f"/records/{record_id}/diagnosis", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "sample"
    assert body["diagnosis"]["source"] == "sample"
    assert body["input_revision"] == 1
    assert body["diagnosis_generation"] == 1


def test_diagnosis_endpoint_requires_location_and_material(
    llm_settings, client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    record_id = record_factory(user_id)["record_id"]
    response = client.post(
        f"/records/{record_id}/diagnosis",
        headers={"Authorization": f"Bearer {token_for(user_id)}"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_diagnosis_endpoint_returns_503_without_model_key(
    client, user_factory, token_for, analyzed_record_factory
):
    user_id = user_factory()
    record_id = analyzed_record_factory(user_id)
    response = client.post(
        f"/records/{record_id}/diagnosis?regenerate=true",
        headers={"Authorization": f"Bearer {token_for(user_id)}"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "llm_unavailable"


def test_diagnosis_endpoint_regenerates_and_stores_llm_result(
    llm_settings, client, user_factory, token_for, analyzed_record_factory, admin, monkeypatch
):
    user_id = user_factory()
    record_id = analyzed_record_factory(user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    monkeypatch.setattr(
        "app.diagnosis.llm.generate_json", lambda *a, **k: _payload()
    )

    response = client.post(
        f"/records/{record_id}/diagnosis?regenerate=true", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "llm"
    assert body["diagnosis"]["severity_level"] == "medium"
    assert body["diagnosis_generation"] == 2
    assert body["input_revision"] == 1

    row = admin.execute(
        "SELECT diagnosis, diagnosis_revision, diagnosis_generation FROM records WHERE id = %s",
        (record_id,),
    ).fetchone()
    assert row["diagnosis"]["source"] == "llm"
    assert row["diagnosis_revision"] == 1
    assert row["diagnosis_generation"] == 2
    detail = client.get(f"/records/{record_id}", headers=headers).json()
    assert detail["diagnosis"]["diagnosis"] == body["diagnosis"]
    assert detail["diagnosis"]["is_current"] is True


@pytest.mark.parametrize(
    "error,status,code",
    [(llm.LlmError, 502, "llm_error"), (llm.LlmTimeout, 504, "llm_timeout")],
)
def test_diagnosis_endpoint_preserves_diagnosis_on_model_failure(
    llm_settings, client, user_factory, token_for, analyzed_record_factory, monkeypatch, error, status, code
):
    user_id = user_factory()
    record_id = analyzed_record_factory(user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    before = client.get(f"/records/{record_id}", headers=headers).json()

    def broken(*_a, **_k):
        raise error

    monkeypatch.setattr("app.diagnosis.llm.generate_json", broken)
    response = client.post(
        f"/records/{record_id}/diagnosis?regenerate=true", headers=headers
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert client.get(f"/records/{record_id}", headers=headers).json() == before


def test_diagnosis_endpoint_returns_409_when_input_changes_during_generation(
    llm_settings, client, user_factory, token_for, analyzed_record_factory, admin, monkeypatch
):
    user_id = user_factory()
    record_id = analyzed_record_factory(user_id)
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}

    def concurrent(record, work_types):
        admin.execute(
            "UPDATE records SET location = %s, input_revision = input_revision + 1 WHERE id = %s",
            ("바뀐 위치", record_id),
        )
        return _normalize(
            _payload(),
            work_types,
            photo_analysis=record.get("photo_observations"),
        )

    monkeypatch.setattr("app.diagnosis.generate_diagnosis", concurrent)
    response = client.post(
        f"/records/{record_id}/diagnosis?regenerate=true", headers=headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "revision_conflict"
    assert response.json()["input_revision"] == 2
    detail = client.get(f"/records/{record_id}", headers=headers).json()
    assert detail["diagnosis"]["diagnosis"]["source"] == "sample"


def test_diagnosis_endpoint_rejects_other_users_record(
    client, user_factory, token_for, analyzed_record_factory
):
    owner_id = user_factory()
    other_id = user_factory()
    record_id = analyzed_record_factory(owner_id)
    response = client.post(
        f"/records/{record_id}/diagnosis",
        headers={"Authorization": f"Bearer {token_for(other_id)}"},
    )
    assert response.status_code == 404


def test_analyze_uses_llm_diagnosis_when_only_llm_is_configured(
    client, user_factory, token_for, record_factory, admin, monkeypatch
):
    settings = SimpleNamespace(
        yolo_model_path=None,
        llm_api_key="test-key",
        llm_model="text-model",
        vision_llm_model=None,
        model_api_key=None,
        sam_timeout_seconds=1,
    )
    monkeypatch.setattr("app.records.get_settings", lambda: settings)
    monkeypatch.setattr("app.vision.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.diagnosis.llm.generate_json", lambda *a, **k: _payload()
    )
    buf = BytesIO()
    Image.new("RGB", (20, 10)).save(buf, format="PNG")
    user_id = user_factory()
    record_id = record_factory(user_id)["record_id"]
    headers = {"Authorization": f"Bearer {token_for(user_id)}"}
    response = client.post(
        f"/records/{record_id}/analyze",
        headers=headers,
        data={
            "photo_roles": "overview",
            "external_analysis_consent": "false",
            "location": "안방 창틀",
            "material": "실리콘",
            "symptoms": "검은 얼룩",
        },
        files=[("photos", ("photo.png", buf.getvalue(), "image/png"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "sample"
    assert body["photo_analysis"]["photos"][0]["status"] == "not_analyzed"
    assert body["diagnosis"]["source"] == "llm"
    assert body["diagnosis"]["severity_level"] == "medium"


def test_analyze_rejects_yolo_without_llm_key(
    client, user_factory, token_for, record_factory, monkeypatch
):
    settings = SimpleNamespace(
        yolo_model_path="models/best.pt",
        llm_api_key=None,
        llm_model="text-model",
        vision_llm_model=None,
        model_api_key=None,
        sam_timeout_seconds=1,
    )
    monkeypatch.setattr("app.records.get_settings", lambda: settings)
    user_id = user_factory()
    record_id = record_factory(user_id)["record_id"]
    response = client.post(
        f"/records/{record_id}/analyze",
        headers={"Authorization": f"Bearer {token_for(user_id)}"},
        data={
            "photo_roles": "overview",
            "external_analysis_consent": "false",
            "location": "안방",
            "material": "벽지",
        },
        files=[("photos", ("photo.png", PNG_1X1, "image/png"))],
    )
    assert response.status_code == 503
    assert response.json()["code"] == "llm_unavailable"
    detail = client.get(
        f"/records/{record_id}",
        headers={"Authorization": f"Bearer {token_for(user_id)}"},
    ).json()
    assert detail["diagnosis"] is None
