import asyncio
from uuid import uuid4

import httpx
from psycopg.types.json import Jsonb

from app import storage
from app.main import app
from conftest import auth_headers


def _region(admin, name="yongin"):
    return admin.execute("SELECT id FROM regions WHERE name = %s", (name,)).fetchone()["id"]


def _work_type(admin, name):
    admin.execute(
        "INSERT INTO work_types (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
        (name,),
    )
    return admin.execute(
        "SELECT id FROM work_types WHERE name = %s", (name,)
    ).fetchone()["id"]


def _profile(client, token, region_id):
    response = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json={
            "nickname": "견적 요청인",
            "region_id": str(region_id),
            "address": None,
            "housing_type": "monthly_rent",
        },
    )
    assert response.status_code == 200, response.text


def _ready_record(
    client,
    admin,
    user_id,
    token,
    record_factory,
    *,
    region_id,
    work_type_id,
    diagnosis=True,
    location="안방 창틀",
    photo_files=None,
):
    record_id = record_factory(user_id)["record_id"]
    admin.execute(
        """
        UPDATE records
        SET location = %s, material = '벽지', symptoms = '검은 얼룩',
            region_id = %s, diagnosis = %s, photo_files = %s
        WHERE id = %s
        """,
        (
            location,
            region_id,
            Jsonb(
                {
                    "severity_score": 72,
                    "severity_level": "high",
                    "suspected_types": ["곰팡이"],
                    "work_type_id": str(work_type_id),
                }
            )
            if diagnosis
            else None,
            Jsonb(photo_files or []),
            record_id,
        ),
    )
    return record_id


def _provider(
    admin,
    name,
    *,
    region_id,
    work_types,
    account_user_id=None,
    rating=4.5,
):
    provider_id = uuid4()
    admin.execute(
        """
        INSERT INTO providers
            (id, name, phone, rating, review_count, account_user_id)
        VALUES (%s, %s, '031-000-0000', %s, 3, %s)
        """,
        (provider_id, name, rating, account_user_id),
    )
    admin.execute(
        "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
        (provider_id, region_id),
    )
    for work_type_id in work_types:
        admin.execute(
            "INSERT INTO provider_work_types (provider_id, work_type_id) VALUES (%s, %s)",
            (provider_id, work_type_id),
        )
    return provider_id


def _create_request(client, token, record_id, **overrides):
    body = {"record_id": str(record_id)}
    body.update(overrides)
    return client.post(
        "/quote-requests", headers=auth_headers(token), json=body
    )


def test_quote_request_create_validation_and_snapshot(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"요청 작업 {uuid4().hex[:8]}")
    user_id = user_factory()
    token = token_for(user_id)
    _profile(client, token, region_id)
    record_id = _ready_record(
        client,
        admin,
        user_id,
        token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
        photo_files=[{"role": "overview", "storage_path": "a/b.jpg", "width": 10, "height": 20}],
    )

    created = _create_request(client, token, record_id)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "open"
    assert body["record_id"] == str(record_id)
    assert body["region_id"] == str(region_id)
    assert body["work_type_id"] == str(work_type_id)
    assert body["location"] == "안방 창틀"
    assert body["material"] == "벽지"
    assert body["memo"] == "검은 얼룩"
    assert body["severity_score"] == 72
    assert body["severity_level"] == "high"
    assert body["suspected_types"] == ["곰팡이"]
    assert body["proposal_count"] == 0
    assert body["proposals"] == []
    assert body["photos"] == []  # Storage key is not configured in tests.

    duplicate = _create_request(client, token, record_id)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "request_already_open"

    missing_diagnosis_record = _ready_record(
        client,
        admin,
        user_factory(),
        token_for(user_factory()),
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
        diagnosis=False,
    )
    # Use the owner token for this record.
    owner_id = admin.execute(
        "SELECT owner_id FROM records WHERE id = %s", (missing_diagnosis_record,)
    ).fetchone()["owner_id"]
    owner_token = token_for(owner_id)
    missing = _create_request(client, owner_token, missing_diagnosis_record)
    assert missing.status_code == 409
    assert missing.json()["code"] == "diagnosis_required"

    no_location = _ready_record(
        client,
        admin,
        user_id,
        token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
        location="",
    )
    assert _create_request(client, token, no_location).status_code == 422


def test_quote_request_create_rejects_provider_and_invalid_region_or_work_type(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"검증 작업 {uuid4().hex[:8]}")
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    _provider(
        admin,
        "요청 거부 업체",
        region_id=region_id,
        work_types=[work_type_id],
        account_user_id=provider_user,
    )
    record_id = _ready_record(
        client,
        admin,
        provider_user,
        provider_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    rejected = _create_request(client, provider_token, record_id)
    assert rejected.status_code == 422

    user_id = user_factory()
    token = token_for(user_id)
    _profile(client, token, region_id)
    record_id = _ready_record(
        client,
        admin,
        user_id,
        token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    invalid_region = _create_request(
        client, token, record_id, region_id=str(uuid4())
    )
    assert invalid_region.status_code == 422
    invalid_work = _create_request(
        client, token, record_id, work_type_id=str(uuid4())
    )
    assert invalid_work.status_code == 422


def test_quote_request_role_lists_and_detail_isolation(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    other_region = admin.execute(
        "INSERT INTO regions (name, display_name) VALUES (%s, %s) RETURNING id",
        (f"r-{uuid4().hex[:8]}", "다른 지역"),
    ).fetchone()["id"]
    work_type_id = _work_type(admin, f"격리 작업 {uuid4().hex[:8]}")
    other_work_type = _work_type(admin, f"다른 작업 {uuid4().hex[:8]}")

    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]

    matched_user = user_factory()
    matched_token = token_for(matched_user)
    _provider(
        admin,
        "매칭 업체",
        region_id=region_id,
        work_types=[work_type_id],
        account_user_id=matched_user,
    )
    wrong_region_user = user_factory()
    _provider(
        admin,
        "타 지역 업체",
        region_id=other_region,
        work_types=[work_type_id],
        account_user_id=wrong_region_user,
    )
    wrong_work_user = user_factory()
    _provider(
        admin,
        "타 분야 업체",
        region_id=region_id,
        work_types=[other_work_type],
        account_user_id=wrong_work_user,
    )

    requester_list = client.get(
        "/quote-requests", headers=auth_headers(requester_token)
    ).json()
    assert [item["request_id"] for item in requester_list] == [request_id]
    assert requester_list[0]["proposal_count"] == 0

    matched_list = client.get(
        "/quote-requests", headers=auth_headers(matched_token)
    ).json()
    assert [item["request_id"] for item in matched_list] == [request_id]
    assert matched_list[0]["proposal_count"] == 0
    assert matched_list[0]["my_proposal_id"] is None
    assert matched_list[0]["requester_nickname"] == "견적 요청인"

    assert (
        client.get(
            f"/quote-requests/{request_id}", headers=auth_headers(matched_token)
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/quote-requests/{request_id}",
            headers=auth_headers(token_for(wrong_region_user)),
        ).status_code
        == 404
    )
    # Same-region providers receive every request regardless of specialty.
    assert (
        client.get(
            f"/quote-requests/{request_id}",
            headers=auth_headers(token_for(wrong_work_user)),
        ).status_code
        == 200
    )
    other_work_list = client.get(
        "/quote-requests", headers=auth_headers(token_for(wrong_work_user))
    ).json()
    assert [item["request_id"] for item in other_work_list] == [request_id]
    assert (
        client.get(
            f"/quote-requests/{request_id}",
            headers=auth_headers(token_for(user_factory())),
        ).status_code
        == 404
    )
    assert (
        client.get(f"/records/{record_id}", headers=auth_headers(matched_token)).status_code
        == 404
    )
    assert client.get("/quote-requests").status_code == 401


def test_proposals_are_isolated_and_accept_rejects_the_rest(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"수락 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]

    provider_users = [user_factory(), user_factory()]
    provider_tokens = [token_for(user) for user in provider_users]
    for index in range(2):
        _provider(
            admin,
            f"제안 업체 {index}",
            region_id=region_id,
            work_types=[work_type_id],
            account_user_id=provider_users[index],
            rating=4.8 - index * 0.1,
        )

    requester_proposal = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(requester_token),
        json={"min_price": 1000, "max_price": 2000, "memo": "요청인 제출"},
    )
    assert requester_proposal.status_code == 422

    non_matching_user = user_factory()
    _provider(
        admin,
        "제안 비매칭 업체",
        region_id=admin.execute(
            "INSERT INTO regions (name, display_name) VALUES (%s, %s) RETURNING id",
            (f"nm-{uuid4().hex[:8]}", "비매칭 지역"),
        ).fetchone()["id"],
        work_types=[work_type_id],
        account_user_id=non_matching_user,
    )
    non_matching = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(token_for(non_matching_user)),
        json={"min_price": 1, "max_price": 2, "memo": "비매칭"},
    )
    assert non_matching.status_code == 404

    proposal_ids = []
    for index, token in enumerate(provider_tokens):
        response = client.post(
            f"/quote-requests/{request_id}/proposals",
            headers=auth_headers(token),
            json={
                "min_price": 100000 + index,
                "max_price": 200000 + index,
                "memo": f"제안 {index}",
            },
        )
        assert response.status_code == 200, response.text
        proposal_ids.append(response.json()["proposal_id"])

    duplicate = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(provider_tokens[0]),
        json={"min_price": 1, "max_price": 2, "memo": "중복"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "proposal_already_exists"

    invalid_price = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(provider_tokens[0]),
        json={"min_price": 5000, "max_price": 1000, "memo": "역전"},
    )
    assert invalid_price.status_code == 422

    owner_detail = client.get(
        f"/quote-requests/{request_id}", headers=auth_headers(requester_token)
    ).json()
    assert len(owner_detail["proposals"]) == 2
    assert all(item["provider"]["region_names"] for item in owner_detail["proposals"])
    assert owner_detail["proposal_count"] == 2
    assert {item["status"] for item in owner_detail["proposals"]} == {"pending"}

    provider_detail = client.get(
        f"/quote-requests/{request_id}", headers=auth_headers(provider_tokens[0])
    ).json()
    assert [item["proposal_id"] for item in provider_detail["proposals"]] == [
        proposal_ids[0]
    ]
    assert provider_detail["proposal_count"] == 0

    accepted = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal_ids[0]}/accept",
        headers=auth_headers(requester_token),
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted"
    assert body["accepted_proposal_id"] == proposal_ids[0]
    statuses = {item["proposal_id"]: item["status"] for item in body["proposals"]}
    assert statuses == {
        proposal_ids[0]: "accepted",
        proposal_ids[1]: "rejected",
    }

    second_accept = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal_ids[1]}/accept",
        headers=auth_headers(requester_token),
    )
    assert second_accept.status_code == 409
    assert second_accept.json()["code"] == "request_not_open"

    late_submit = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(provider_tokens[0]),
        json={"min_price": 1, "max_price": 2, "memo": "마감 후"},
    )
    assert late_submit.status_code == 409
    assert late_submit.json()["code"] == "request_not_open"

    provider_after = client.get(
        f"/quote-requests/{request_id}", headers=auth_headers(provider_tokens[1])
    ).json()
    assert provider_after["proposals"][0]["status"] == "rejected"


def test_cancel_rejects_pending_proposals(client, admin, user_factory, token_for, record_factory):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"취소 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    _provider(
        admin,
        "취소 제안 업체",
        region_id=region_id,
        work_types=[work_type_id],
        account_user_id=provider_user,
    )
    proposal = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(provider_token),
        json={"min_price": 1000, "max_price": 2000, "memo": "취소 전 제안"},
    )
    assert proposal.status_code == 200

    cancelled = client.post(
        f"/quote-requests/{request_id}/cancel", headers=auth_headers(requester_token)
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["proposals"][0]["status"] == "rejected"

    again = client.post(
        f"/quote-requests/{request_id}/cancel", headers=auth_headers(requester_token)
    )
    assert again.status_code == 409
    assert again.json()["code"] == "request_not_open"


def test_cancel_accept_reopens_request_and_proposals(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"수락 취소 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]
    proposal_ids = []
    for index in range(2):
        provider_user = user_factory()
        _provider(
            admin,
            f"수락 취소 업체 {index}",
            region_id=region_id,
            work_types=[work_type_id],
            account_user_id=provider_user,
        )
        response = client.post(
            f"/quote-requests/{request_id}/proposals",
            headers=auth_headers(token_for(provider_user)),
            json={"min_price": 1000, "max_price": 2000, "memo": f"제안 {index}"},
        )
        assert response.status_code == 200, response.text
        proposal_ids.append(response.json()["proposal_id"])

    not_accepted = client.post(
        f"/quote-requests/{request_id}/cancel-accept", headers=auth_headers(requester_token)
    )
    assert not_accepted.status_code == 409
    assert not_accepted.json()["code"] == "request_not_accepted"

    accepted = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal_ids[0]}/accept",
        headers=auth_headers(requester_token),
    )
    assert accepted.status_code == 200, accepted.text

    reopened = client.post(
        f"/quote-requests/{request_id}/cancel-accept", headers=auth_headers(requester_token)
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["status"] == "open"
    assert body["accepted_proposal_id"] is None
    assert {item["status"] for item in body["proposals"]} == {"pending"}

    other = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal_ids[1]}/accept",
        headers=auth_headers(requester_token),
    )
    assert other.status_code == 200, other.text
    assert other.json()["accepted_proposal_id"] == proposal_ids[1]


def test_complete_closes_accepted_request(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"거래 완료 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]
    provider_user = user_factory()
    _provider(
        admin,
        "거래 완료 업체",
        region_id=region_id,
        work_types=[work_type_id],
        account_user_id=provider_user,
    )
    proposal = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(token_for(provider_user)),
        json={"min_price": 1000, "max_price": 2000, "memo": "완료 제안"},
    )
    assert proposal.status_code == 200, proposal.text

    not_accepted = client.post(
        f"/quote-requests/{request_id}/complete", headers=auth_headers(requester_token)
    )
    assert not_accepted.status_code == 409
    assert not_accepted.json()["code"] == "request_not_accepted"

    accepted = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal.json()['proposal_id']}/accept",
        headers=auth_headers(requester_token),
    )
    assert accepted.status_code == 200, accepted.text

    other_user = client.post(
        f"/quote-requests/{request_id}/complete",
        headers=auth_headers(token_for(user_factory())),
    )
    assert other_user.status_code == 404

    completed = client.post(
        f"/quote-requests/{request_id}/complete", headers=auth_headers(requester_token)
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    vendor_list = client.get("/quote-requests", headers=auth_headers(token_for(provider_user)))
    assert vendor_list.status_code == 200
    assert [item["status"] for item in vendor_list.json() if item["request_id"] == request_id] == [
        "completed"
    ]

    for path in ("cancel-accept", "complete", "cancel"):
        again = client.post(
            f"/quote-requests/{request_id}/{path}", headers=auth_headers(requester_token)
        )
        assert again.status_code == 409, path


def test_concurrent_accept_has_one_winner(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"동시 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]
    proposal_ids = []
    for index in range(2):
        provider_user = user_factory()
        provider_token = token_for(provider_user)
        _provider(
            admin,
            f"동시 업체 {index}",
            region_id=region_id,
            work_types=[work_type_id],
            account_user_id=provider_user,
        )
        response = client.post(
            f"/quote-requests/{request_id}/proposals",
            headers=auth_headers(provider_token),
            json={"min_price": 1000, "max_price": 2000, "memo": f"동시 {index}"},
        )
        assert response.status_code == 200
        proposal_ids.append(response.json()["proposal_id"])

    async def accept(proposal_id):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            return await async_client.post(
                f"/quote-requests/{request_id}/proposals/{proposal_id}/accept",
                headers=auth_headers(requester_token),
            )

    async def scenario():
        return await asyncio.gather(*(accept(proposal_id) for proposal_id in proposal_ids))

    responses = asyncio.run(scenario())
    assert sorted(response.status_code for response in responses) == [200, 409]


def test_chat_room_can_open_before_and_after_accept(
    client, admin, user_factory, token_for, record_factory
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"채팅 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
    )
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(
        admin,
        "채팅 가능 업체",
        region_id=region_id,
        work_types=[work_type_id],
        account_user_id=provider_user,
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]
    proposal = client.post(
        f"/quote-requests/{request_id}/proposals",
        headers=auth_headers(provider_token),
        json={"min_price": 1000, "max_price": 2000, "memo": "채팅 전 제안"},
    ).json()

    before = client.post(
        "/chat/rooms",
        headers=auth_headers(requester_token),
        json={"provider_id": str(provider_id), "record_id": str(record_id)},
    )
    assert before.status_code == 200, before.text

    accepted = client.post(
        f"/quote-requests/{request_id}/proposals/{proposal['proposal_id']}/accept",
        headers=auth_headers(requester_token),
    )
    assert accepted.status_code == 200

    after = client.post(
        "/chat/rooms",
        headers=auth_headers(requester_token),
        json={"provider_id": str(provider_id), "record_id": str(record_id)},
    )
    assert after.status_code == 200, after.text


def test_quote_photos_use_signed_urls_for_authorized_viewers(
    client, admin, user_factory, token_for, record_factory, monkeypatch
):
    region_id = _region(admin)
    work_type_id = _work_type(admin, f"사진 작업 {uuid4().hex[:8]}")
    requester_id = user_factory()
    requester_token = token_for(requester_id)
    _profile(client, requester_token, region_id)
    record_id = _ready_record(
        client,
        admin,
        requester_id,
        requester_token,
        record_factory,
        region_id=region_id,
        work_type_id=work_type_id,
        photo_files=[
            {
                "role": "overview",
                "storage_path": "a/b.jpg",
                "width": 10,
                "height": 20,
            }
        ],
    )
    monkeypatch.setattr(storage, "is_configured", lambda: True)
    monkeypatch.setattr(
        storage,
        "signed_photos",
        lambda _files: [
            {
                "role": "overview",
                "url": "https://project.supabase.co/signed",
                "expires_at": "2026-01-01T00:00:00Z",
                "width": 10,
                "height": 20,
            }
        ],
    )
    request_id = _create_request(client, requester_token, record_id).json()["request_id"]

    detail = client.get(
        f"/quote-requests/{request_id}", headers=auth_headers(requester_token)
    ).json()
    assert detail["photos"][0]["url"].endswith("/signed")
    assert detail["photos"][0]["role"] == "overview"
