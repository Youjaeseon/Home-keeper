import asyncio
from uuid import uuid4

import httpx
import pytest
from starlette.websockets import WebSocketDisconnect

from app.chat import ChatConnectionHub
from app.main import app
from conftest import auth_headers


def _yongin_id(admin):
    return admin.execute("SELECT id FROM regions WHERE name = 'yongin'").fetchone()["id"]


def _provider(admin, name="용인 수리 업체", phone="031-123-4567", account_user_id=None):
    provider_id = uuid4()
    admin.execute(
        "INSERT INTO providers (id, name, phone, account_user_id) VALUES (%s, %s, %s, %s)",
        (provider_id, name, phone, account_user_id),
    )
    admin.execute(
        "INSERT INTO provider_regions (provider_id, region_id) VALUES (%s, %s)",
        (provider_id, _yongin_id(admin)),
    )
    return provider_id


def _profile(client, token, admin, *, nickname="요청인", address="용인시 수지구 비밀주소 1"):
    response = client.put(
        "/me/profile",
        headers=auth_headers(token),
        json={
            "nickname": nickname,
            "region_id": str(_yongin_id(admin)),
            "address": address,
            "housing_type": "monthly_rent",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _room(client, token, provider_id, record_id=None):
    body = {"provider_id": str(provider_id)}
    if record_id is not None:
        body["record_id"] = str(record_id)
    return client.post("/chat/rooms", headers=auth_headers(token), json=body)


def _send(client, token, room_id, content, client_message_id=None):
    return client.post(
        f"/chat/rooms/{room_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(client_message_id or uuid4()),
            "content": content,
        },
    )


def _messages(client, token, room_id, **params):
    return client.get(
        f"/chat/rooms/{room_id}/messages",
        headers=auth_headers(token),
        params=params,
    )


def test_chat_endpoints_require_auth(client):
    room_id, client_message_id = uuid4(), uuid4()
    assert client.get("/chat/rooms").status_code == 401
    assert client.post(
        "/chat/rooms", json={"provider_id": str(uuid4())}
    ).status_code == 401
    assert client.get(f"/chat/rooms/{room_id}/messages").status_code == 401
    assert client.post(
        f"/chat/rooms/{room_id}/messages",
        json={"client_message_id": str(client_message_id), "content": "안녕하세요"},
    ).status_code == 401


def test_room_creation_requires_linked_provider_and_owned_record(
    client, admin, user_factory, token_for, analyzed_record_factory
):
    requester = user_factory()
    token = token_for(requester)
    unlinked = _provider(admin, "전화만 되는 업체", account_user_id=None)
    linked_user = user_factory()
    linked = _provider(admin, "채팅 업체", account_user_id=linked_user)

    response = _room(client, token, unlinked)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_request"

    sample = _room(client, token, "00000000-0000-4000-8000-000000000001")
    assert sample.status_code == 404, sample.text

    other_record = analyzed_record_factory(user_factory())
    foreign = _room(client, token, linked, other_record)
    assert foreign.status_code == 404, foreign.text
    assert foreign.json()["code"] == "not_found"
    assert admin.execute(
        "SELECT count(*) AS c FROM chat_rooms WHERE requester_id = %s", (requester,)
    ).fetchone()["c"] == 0

    provider_account_token = token_for(linked_user)
    as_provider = _room(client, provider_account_token, linked)
    assert as_provider.status_code == 422, as_provider.text
    assert as_provider.json()["code"] == "invalid_request"


def test_room_reuse_and_record_summary_sharing(
    client, admin, user_factory, token_for, analyzed_record_factory
):
    requester = user_factory()
    token = token_for(requester)
    profile = _profile(client, token, admin, nickname="요청인 닉네임")
    first_record = analyzed_record_factory(requester)
    second_record = analyzed_record_factory(
        requester, location="욕실 천장", material="도장면", symptoms="벗겨짐과 물얼룩"
    )
    provider_id = _provider(admin, "용인 곰팡이 수리", account_user_id=user_factory())

    created = _room(client, token, provider_id, first_record)
    assert created.status_code == 200, created.text
    room = created.json()
    assert room["provider_name"] == "용인 곰팡이 수리"
    assert room["requester_id"] == str(requester)
    assert room["provider_id"] == str(provider_id)
    assert room["latest_record_id"] == str(first_record)

    messages = _messages(client, token, room["room_id"]).json()
    assert len(messages["messages"]) == 1
    summary = messages["messages"][0]
    assert summary["message_type"] == "record_summary"
    assert summary["sender_role"] == "requester"
    assert summary["sender_id"] == str(requester)
    assert summary["record_id"] == str(first_record)
    assert summary["content"].startswith("[하자 분석 요약]")
    assert "안방 창틀 아래" in summary["content"]
    assert summary["payload"]["material"] == "실리콘"
    assert summary["payload"]["suspected_types"] == ["곰팡이"]
    assert summary["payload"]["severity_level"] in {"low", "medium", "high"}
    for forbidden in ("address", "email", "nickname", "housing_type", "photo"):
        assert forbidden not in summary["payload"]
    assert profile["address"] not in str(messages)

    repeated = _room(client, token, provider_id, first_record)
    assert repeated.status_code == 200
    assert repeated.json()["room_id"] == room["room_id"]
    assert len(_messages(client, token, room["room_id"]).json()["messages"]) == 1
    assert admin.execute(
        "SELECT count(*) AS c FROM chat_rooms WHERE requester_id = %s", (requester,)
    ).fetchone()["c"] == 1

    shared_second = _room(client, token, provider_id, second_record)
    assert shared_second.status_code == 200
    assert shared_second.json()["room_id"] == room["room_id"]
    assert shared_second.json()["latest_record_id"] == str(second_record)
    messages = _messages(client, token, room["room_id"]).json()["messages"]
    assert [message["record_id"] for message in messages] == [
        str(first_record),
        str(second_record),
    ]
    assert messages[1]["payload"]["location"] == "욕실 천장"


def test_room_creation_rejects_client_supplied_summary(
    client, admin, user_factory, token_for, analyzed_record_factory
):
    requester = user_factory()
    token = token_for(requester)
    record_id = analyzed_record_factory(requester)
    provider_id = _provider(admin, account_user_id=user_factory())

    response = client.post(
        "/chat/rooms",
        headers=auth_headers(token),
        json={
            "provider_id": str(provider_id),
            "record_id": str(record_id),
            "record_summary": "임의로 만든 요약",
        },
    )
    assert response.status_code == 422
    assert admin.execute(
        "SELECT count(*) AS c FROM chat_rooms WHERE requester_id = %s", (requester,)
    ).fetchone()["c"] == 0


def test_concurrent_room_creation_keeps_a_single_room(
    client, admin, user_factory, token_for
):
    requester = user_factory()
    token = token_for(requester)
    provider_id = _provider(admin, account_user_id=user_factory())

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            return await asyncio.gather(
                *[
                    ac.post(
                        "/chat/rooms",
                        headers=auth_headers(token),
                        json={"provider_id": str(provider_id)},
                    )
                    for _ in range(2)
                ]
            )

    first, second = asyncio.run(scenario())
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["room_id"] == second.json()["room_id"]
    assert admin.execute(
        "SELECT count(*) AS c FROM chat_rooms WHERE requester_id = %s", (requester,)
    ).fetchone()["c"] == 1


def test_only_participants_can_access_rooms_and_messages(
    client, admin, user_factory, token_for, analyzed_record_factory
):
    requester = user_factory()
    requester_token = token_for(requester)
    _profile(client, requester_token, admin, nickname="요청인 닉네임")
    record_id = analyzed_record_factory(requester)

    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(admin, "참여 업체", account_user_id=provider_user)

    outsider = user_factory()
    outsider_token = token_for(outsider)
    other_provider_user = user_factory()
    other_provider_token = token_for(other_provider_user)
    _provider(admin, "다른 업체", account_user_id=other_provider_user)

    room_id = _room(client, requester_token, provider_id, record_id).json()["room_id"]

    assert len(_messages(client, requester_token, room_id).json()["messages"]) == 1
    assert len(_messages(client, provider_token, room_id).json()["messages"]) == 1

    for token in (outsider_token, other_provider_token):
        assert _messages(client, token, room_id).status_code == 404
        assert _send(client, token, room_id, "몰래 보낸 메시지").status_code == 404
    assert _messages(client, outsider_token, room_id).json()["code"] == "not_found"

    assert client.get("/chat/rooms", headers=auth_headers(outsider_token)).json() == []
    assert client.get(
        "/chat/rooms", headers=auth_headers(other_provider_token)
    ).json() == []

    requester_rooms = client.get(
        "/chat/rooms", headers=auth_headers(requester_token)
    ).json()
    assert len(requester_rooms) == 1
    assert requester_rooms[0]["counterpart_name"] == "참여 업체"
    assert requester_rooms[0]["last_message_preview"].startswith("[하자 분석 요약]")

    provider_rooms = client.get("/chat/rooms", headers=auth_headers(provider_token)).json()
    assert len(provider_rooms) == 1
    assert provider_rooms[0]["counterpart_name"] == "요청인 닉네임"
    assert "용인시 수지구 비밀주소 1" not in str(provider_rooms)

    # A provider never gains access to the source record or the requester profile.
    assert client.get(
        f"/records/{record_id}", headers=auth_headers(provider_token)
    ).status_code == 404
    assert client.get(
        "/me/profile", headers=auth_headers(provider_token)
    ).status_code == 404


def test_message_idempotency_conflict_and_validation(
    client, admin, user_factory, token_for
):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(admin, account_user_id=provider_user)
    room_id = _room(client, requester_token, provider_id).json()["room_id"]

    client_message_id = uuid4()
    first = _send(client, requester_token, room_id, "  안녕하세요  ", client_message_id)
    assert first.status_code == 200, first.text
    message = first.json()
    assert message["content"] == "안녕하세요"
    assert message["sender_role"] == "requester"
    assert message["sender_id"] == str(requester)
    assert message["message_type"] == "text"
    assert message["record_id"] is None
    assert message["payload"] is None

    resent = _send(client, requester_token, room_id, "안녕하세요", client_message_id)
    assert resent.status_code == 200
    assert resent.json()["message_id"] == message["message_id"]
    assert admin.execute(
        "SELECT count(*) AS c FROM chat_messages WHERE room_id = %s", (room_id,)
    ).fetchone()["c"] == 1

    conflict = _send(client, requester_token, room_id, "다른 내용", client_message_id)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "message_conflict"

    reply = _send(client, provider_token, room_id, "네, 내일 방문 가능합니다")
    assert reply.status_code == 200, reply.text
    assert reply.json()["sender_role"] == "provider"
    assert reply.json()["sender_id"] == str(provider_user)

    for body in (
        {"client_message_id": str(uuid4()), "content": "   "},
        {"client_message_id": str(uuid4()), "content": ""},
        {"client_message_id": str(uuid4()), "content": "x" * 2001},
        {
            "client_message_id": str(uuid4()),
            "content": "정상",
            "sender_role": "provider",
        },
        {
            "client_message_id": str(uuid4()),
            "content": "정상",
            "sender_id": str(provider_user),
        },
    ):
        assert client.post(
            f"/chat/rooms/{room_id}/messages",
            headers=auth_headers(requester_token),
            json=body,
        ).status_code == 422

    longest = _send(client, requester_token, room_id, "x" * 2000)
    assert longest.status_code == 200, longest.text

    rooms = client.get("/chat/rooms", headers=auth_headers(requester_token)).json()
    assert rooms[0]["last_message_preview"] == "x" * 80


def test_message_ordering_and_pagination(
    client, admin, user_factory, token_for
):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_id = _provider(admin, account_user_id=user_factory())
    room_id = _room(client, requester_token, provider_id).json()["room_id"]

    for index in range(3):
        assert _send(client, requester_token, room_id, f"메시지 {index}").status_code == 200

    all_messages = _messages(client, requester_token, room_id).json()
    assert all_messages["limit"] == 50
    assert all_messages["offset"] == 0
    assert all_messages["has_more"] is False
    assert [item["content"] for item in all_messages["messages"]] == [
        "메시지 0",
        "메시지 1",
        "메시지 2",
    ]

    first_page = _messages(client, requester_token, room_id, limit=2).json()
    assert [item["content"] for item in first_page["messages"]] == ["메시지 0", "메시지 1"]
    assert first_page["has_more"] is True

    second_page = _messages(client, requester_token, room_id, limit=2, offset=2).json()
    assert [item["content"] for item in second_page["messages"]] == ["메시지 2"]
    assert second_page["has_more"] is False

    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert _messages(client, requester_token, room_id, **params).status_code == 422


def test_room_list_orders_by_latest_message(client, admin, user_factory, token_for):
    requester = user_factory()
    requester_token = token_for(requester)
    first_provider = _provider(admin, "첫 업체", account_user_id=user_factory())
    second_provider = _provider(admin, "둘째 업체", account_user_id=user_factory())

    first_room = _room(client, requester_token, first_provider).json()["room_id"]
    second_room = _room(client, requester_token, second_provider).json()["room_id"]
    assert _send(client, requester_token, first_room, "첫 방 메시지").status_code == 200
    assert _send(client, requester_token, second_room, "둘째 방 메시지").status_code == 200

    rooms = client.get("/chat/rooms", headers=auth_headers(requester_token)).json()
    assert [room["room_id"] for room in rooms[:2]] == [second_room, first_room]
    assert rooms[0]["last_message_preview"] == "둘째 방 메시지"


def _rooms(client, token):
    response = client.get("/chat/rooms", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def _read(client, token, room_id):
    return client.post(
        f"/chat/rooms/{room_id}/read", headers=auth_headers(token)
    )


def test_room_unread_counts_and_read_receipt(
    client, admin, user_factory, token_for, analyzed_record_factory
):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(admin, account_user_id=provider_user)
    outsider_token = token_for(user_factory())

    record_id = analyzed_record_factory(requester)
    room_id = _room(client, requester_token, provider_id, record_id).json()["room_id"]

    # The record summary is sent by the requester: unread for the provider only.
    assert _rooms(client, requester_token)[0]["unread_count"] == 0
    assert _rooms(client, provider_token)[0]["unread_count"] == 1

    receipt = _read(client, provider_token, room_id)
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["room_id"] == room_id
    assert receipt.json()["unread_count"] == 0
    assert receipt.json()["last_read_at"]
    assert _rooms(client, provider_token)[0]["unread_count"] == 0

    for content in ("첫 질문", "둘째 질문"):
        assert _send(client, requester_token, room_id, content).status_code == 200
    # Own messages never count; the provider sees both new messages.
    assert _rooms(client, requester_token)[0]["unread_count"] == 0
    assert _rooms(client, provider_token)[0]["unread_count"] == 2

    assert _read(client, provider_token, room_id).json()["unread_count"] == 0
    assert _send(client, provider_token, room_id, "업체 답장").status_code == 200
    assert _rooms(client, requester_token)[0]["unread_count"] == 1
    assert _rooms(client, provider_token)[0]["unread_count"] == 0
    assert _read(client, requester_token, room_id).json()["unread_count"] == 0
    assert _rooms(client, requester_token)[0]["unread_count"] == 0

    assert _read(client, outsider_token, room_id).status_code == 404
    assert _read(client, requester_token, uuid4()).status_code == 404


def test_chat_websocket_rejects_missing_or_invalid_token(client):
    for path in ("/chat/ws", "/chat/ws?access_token=not-a-token"):
        with client.websocket_connect(path) as websocket:
            with pytest.raises(WebSocketDisconnect) as closed:
                websocket.receive_json()
            assert closed.value.code == 4401


def test_chat_websocket_pushes_to_both_participants_and_reconnects(
    client, admin, user_factory, token_for
):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(admin, account_user_id=provider_user)
    room_id = _room(client, requester_token, provider_id).json()["room_id"]

    with client.websocket_connect(
        f"/chat/ws?access_token={requester_token}"
    ) as requester_ws, client.websocket_connect(
        f"/chat/ws?access_token={provider_token}"
    ) as provider_ws:
        assert requester_ws.receive_json() == {
            "type": "ready",
            "user_id": str(requester),
        }
        assert provider_ws.receive_json() == {
            "type": "ready",
            "user_id": str(provider_user),
        }

        sent = _send(client, requester_token, room_id, "실시간 확인")
        assert sent.status_code == 200, sent.text
        message = sent.json()
        for websocket in (requester_ws, provider_ws):
            event = websocket.receive_json()
            assert event["type"] == "message"
            assert event["room_id"] == room_id
            assert event["message"] == message

    # A reconnect gets a fresh ready event and subsequent messages; missed
    # messages are recovered through the REST history endpoint.
    with client.websocket_connect(
        f"/chat/ws?access_token={provider_token}"
    ) as reconnected:
        assert reconnected.receive_json()["type"] == "ready"
        assert _send(client, requester_token, room_id, "재연결 후").status_code == 200
        event = reconnected.receive_json()
        assert event["message"]["content"] == "재연결 후"


def test_chat_websocket_does_not_duplicate_idempotent_resends(
    client, admin, user_factory, token_for
):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_id = _provider(admin, account_user_id=user_factory())
    room_id = _room(client, requester_token, provider_id).json()["room_id"]
    client_message_id = uuid4()

    with client.websocket_connect(
        f"/chat/ws?access_token={requester_token}"
    ) as websocket:
        assert websocket.receive_json()["type"] == "ready"
        assert _send(
            client, requester_token, room_id, "한 번만", client_message_id
        ).status_code == 200
        assert websocket.receive_json()["message"]["content"] == "한 번만"

        assert _send(
            client, requester_token, room_id, "한 번만", client_message_id
        ).status_code == 200
        assert _send(client, requester_token, room_id, "다음 메시지").status_code == 200
        assert websocket.receive_json()["message"]["content"] == "다음 메시지"


def test_chat_websocket_pushes_new_record_summary(client, admin, user_factory, token_for, analyzed_record_factory):
    requester = user_factory()
    requester_token = token_for(requester)
    provider_user = user_factory()
    provider_token = token_for(provider_user)
    provider_id = _provider(admin, account_user_id=provider_user)
    record_id = analyzed_record_factory(requester)

    with client.websocket_connect(
        f"/chat/ws?access_token={provider_token}"
    ) as provider_ws:
        assert provider_ws.receive_json()["type"] == "ready"
        created = _room(client, requester_token, provider_id, record_id)
        assert created.status_code == 200, created.text
        event = provider_ws.receive_json()
        assert event["type"] == "message"
        assert event["message"]["message_type"] == "record_summary"
        assert event["message"]["record_id"] == str(record_id)


class _FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


def test_chat_hub_broadcast_targets_only_requested_users():
    requester_id, provider_id, outsider_id = uuid4(), uuid4(), uuid4()

    async def scenario():
        hub = ChatConnectionHub()
        requester, provider, outsider = _FakeSocket(), _FakeSocket(), _FakeSocket()
        await hub.connect(requester_id, requester)
        await hub.connect(provider_id, provider)
        await hub.connect(outsider_id, outsider)
        await hub.broadcast(
            {requester_id, provider_id}, {"type": "message", "room_id": "room"}
        )
        await hub.disconnect(requester_id, requester)
        await hub.broadcast({requester_id, provider_id}, {"type": "message"})
        return requester.sent, provider.sent, outsider.sent

    requester_sent, provider_sent, outsider_sent = asyncio.run(scenario())
    assert len(requester_sent) == 1
    assert len(provider_sent) == 2
    assert outsider_sent == []
