import asyncio
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.main import app
from conftest import auth_headers


def _post_message(client, token, record_id, payload):
    return client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json=payload,
    )


def _get_record(client, token, record_id):
    return client.get(f"/records/{record_id}", headers=auth_headers(token))


def _setup_conversation(client, token, record_factory, question_factory, user_id):
    record_id = record_factory(user_id)["record_id"]
    q1 = question_factory(record_id, "첫 질문")
    first = client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(uuid4()),
            "question_id": str(q1),
            "content": "첫 답변",
            "input_revision": 0,
        },
    )
    assert first.status_code == 200, first.text
    q2 = question_factory(record_id, "두 번째 질문")
    second = client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(uuid4()),
            "question_id": str(q2),
            "content": "두 번째 답변",
            "input_revision": 1,
        },
    )
    assert second.status_code == 200, second.text
    return (
        record_id,
        q1,
        first.json()["message"],
        q2,
        second.json()["message"],
    )


def _run_concurrently(requests):
    async def run():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            return await asyncio.gather(*requests(async_client))

    return asyncio.run(run())


def test_create_and_get_empty_record(client, user_factory, token_for, record_factory):
    user_id = user_factory()
    token = token_for(user_id)
    created = record_factory(user_id)

    response = _get_record(client, token, created["record_id"])
    assert response.status_code == 200
    body = response.json()
    assert body["record_id"] == created["record_id"]
    assert body["input_revision"] == 0
    assert body["location"] is None
    assert body["questions"] == []
    assert body["messages"] == []
    assert body["diagnosis"] is None
    assert body["next_question"] is None
    assert body["drafts"] == {"landlord": None, "provider": None}


def test_missing_record_returns_404(client, user_factory, token_for):
    user_id = user_factory()
    token = token_for(user_id)
    missing = uuid4()
    assert _get_record(client, token, missing).status_code == 404
    assert (
        client.patch(
            f"/records/{missing}",
            headers=auth_headers(token),
            json={"location": "어딘가"},
        ).status_code
        == 404
    )


def test_patch_only_bumps_revision_on_real_change(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    url = f"/records/{record_id}"

    first = client.patch(
        url,
        headers=auth_headers(token),
        json={"location": "창가", "symptoms": "검은 얼룩"},
    )
    assert first.status_code == 200
    assert first.json()["input_revision"] == 1

    same = client.patch(
        url,
        headers=auth_headers(token),
        json={"location": "창가", "symptoms": "검은 얼룩"},
    )
    assert same.status_code == 200
    assert same.json()["input_revision"] == 1

    cleared = client.patch(
        url, headers=auth_headers(token), json={"location": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["input_revision"] == 2
    assert cleared.json()["location"] is None
    assert cleared.json()["symptoms"] == "검은 얼룩"

    empty = client.patch(url, headers=auth_headers(token), json={})
    assert empty.status_code == 422


def test_selected_option_saves_server_label(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(
        record_id,
        "다시 생겼나요?",
        [
            {"id": "recurred", "label": "다시 생겼어요"},
            {"id": "first_seen", "label": "처음 발견했어요"},
        ],
    )

    response = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(question_id),
            "selected_option_id": "recurred",
            "input_revision": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "다시 생겼어요"
    assert body["message"]["sender"] == "user"
    assert body["message"]["sequence"] == 2
    assert body["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert detail["input_revision"] == 1
    assert len(detail["messages"]) == 1
    assert detail["questions"][0]["answered"] is False


def test_direct_content_is_saved_as_sent(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(record_id, "어디인가요?")

    response = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(question_id),
            "content": "  창틀 아래쪽이에요  ",
            "input_revision": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["message"]["content"] == "  창틀 아래쪽이에요  "


def test_answer_requires_exactly_one_of_content_or_option(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(
        record_id, "질문", [{"id": "yes", "label": "네"}]
    )
    base = {
        "client_message_id": str(uuid4()),
        "question_id": str(question_id),
        "input_revision": 0,
    }

    for payload in (
        base,
        {**base, "content": "직접", "selected_option_id": "yes"},
        {**base, "content": "   "},
        {**base, "selected_option_id": "yes", "question_id": None},
    ):
        response = _post_message(client, token, record_id, payload)
        assert response.status_code == 422, response.text


def test_unknown_option_is_rejected(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(
        record_id, "질문", [{"id": "yes", "label": "네"}]
    )

    response = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(question_id),
            "selected_option_id": "no",
            "input_revision": 0,
        },
    )
    assert response.status_code == 422
    assert _get_record(client, token, record_id).json()["messages"] == []


def test_question_from_another_record_is_rejected(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    other_record_id = record_factory(user_id)["record_id"]
    other_question = question_factory(other_record_id, "다른 기록 질문")

    response = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(other_question),
            "content": "답변",
            "input_revision": 0,
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert _get_record(client, token, record_id).json()["messages"] == []
    assert (
        _get_record(client, token, record_id).json()["input_revision"] == 0
    )

    missing_question = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(uuid4()),
            "content": "답변",
            "input_revision": 0,
        },
    )
    assert missing_question.status_code == 404


def test_same_client_message_id_replay_is_idempotent(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(
        record_id,
        "질문",
        [
            {"id": "recurred", "label": "다시 생겼어요"},
            {"id": "first_seen", "label": "처음 발견했어요"},
        ],
    )
    payload = {
        "client_message_id": str(uuid4()),
        "question_id": str(question_id),
        "selected_option_id": "recurred",
        "input_revision": 0,
    }

    first = _post_message(client, token, record_id, payload)
    second = _post_message(client, token, record_id, payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["message"]["id"] == second.json()["message"]["id"]
    assert first.json()["input_revision"] == second.json()["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert len(detail["messages"]) == 1
    assert detail["input_revision"] == 1

    different_content = _post_message(
        client,
        token,
        record_id,
        {**payload, "selected_option_id": None, "content": "다른 답"},
    )
    assert different_content.status_code == 409
    assert different_content.json()["code"] == "message_conflict"

    different_option = _post_message(
        client, token, record_id, {**payload, "selected_option_id": "first_seen"}
    )
    assert different_option.status_code == 409

    different_question = _post_message(
        client,
        token,
        record_id,
        {
            **payload,
            "question_id": None,
            "selected_option_id": None,
            "content": "다른 답",
        },
    )
    assert different_question.status_code == 409


def test_stale_input_revision_is_rejected(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(record_id, "질문")

    assert (
        _post_message(
            client,
            token,
            record_id,
            {
                "client_message_id": str(uuid4()),
                "question_id": str(question_id),
                "content": "첫 답",
                "input_revision": 0,
            },
        ).status_code
        == 200
    )

    stale = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(question_id),
            "content": "늦은 답",
            "input_revision": 0,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "revision_conflict"
    assert stale.json()["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert len(detail["messages"]) == 1
    assert detail["input_revision"] == 1


@pytest.mark.parametrize(
    ("first_answer", "other_answer"),
    [
        ({"selected_option_id": "a"}, {"selected_option_id": "b"}),
        ({"selected_option_id": "a"}, {"content": "같은 문구"}),
        ({"content": "같은 문구"}, {"selected_option_id": "a"}),
    ],
)
def test_replay_distinguishes_answers_with_the_same_label(
    client, user_factory, token_for, record_factory, question_factory,
    first_answer, other_answer,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(
        record_id, "질문",
        [{"id": "a", "label": "같은 문구"}, {"id": "b", "label": "같은 문구"}],
    )
    base = {
        "client_message_id": str(uuid4()),
        "question_id": str(question_id),
        "input_revision": 0,
    }
    first = _post_message(client, token, record_id, {**base, **first_answer})
    assert first.status_code == 200
    assert "selected_option_id" not in first.json()["message"]
    assert "submitted_content" not in first.json()["message"]
    replay = _post_message(client, token, record_id, {**base, **first_answer})
    assert replay.json() == first.json()

    conflict = _post_message(client, token, record_id, {**base, **other_answer})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "message_conflict"
    assert conflict.json()["input_revision"] == 1
    detail = _get_record(client, token, record_id).json()
    assert len(detail["messages"]) == 1
    assert detail["input_revision"] == 1


@pytest.mark.parametrize("answer", [{"content": "원래 답변"}, {"selected_option_id": "a"}])
def test_replay_after_edit_compares_original_submission(
    client, user_factory, token_for, record_factory, question_factory, answer,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(record_id, "질문", [{"id": "a", "label": "원래 답변"}])
    payload = {
        "client_message_id": str(uuid4()),
        "question_id": str(question_id),
        "input_revision": 0,
        **answer,
    }
    first = _post_message(client, token, record_id, payload)
    assert first.status_code == 200
    edited = client.put(
        f"/records/{record_id}/messages/{first.json()['message']['id']}",
        headers=auth_headers(token),
        json={"content": "수정한 답변", "input_revision": 1},
    )
    assert edited.status_code == 200
    replay = _post_message(client, token, record_id, payload)
    assert replay.status_code == 200
    assert replay.json() == edited.json()
    changed = {**payload, "selected_option_id": None, "content": "수정한 답변"}
    assert _post_message(client, token, record_id, changed).status_code == 409


def test_legacy_message_replay_conflicts_without_guessing_input_mode(
    client, user_factory, token_for, record_factory, admin,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    client_id = uuid4()
    admin.execute(
        """
        INSERT INTO messages
            (record_id, sequence, sender, content, client_message_id, input_revision)
        VALUES (%s, 1, 'user', '기존 답변', %s, 0)
        """,
        (record_id, client_id),
    )
    replay = _post_message(client, token, record_id, {
        "client_message_id": str(client_id), "content": "기존 답변", "input_revision": 0,
    })
    assert replay.status_code == 409
    assert replay.json()["code"] == "message_conflict"
    assert _get_record(client, token, record_id).json()["messages"][0]["content"] == "기존 답변"


def test_editing_past_message_deletes_later_conversation(
    client,
    user_factory,
    token_for,
    record_factory,
    question_factory,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, q1, m1, q2, m2 = _setup_conversation(
        client, token, record_factory, question_factory, user_id
    )
    assert [q["sequence"] for q in _get_record(client, token, record_id).json()["questions"]] == [1, 3]
    assert [m["sequence"] for m in _get_record(client, token, record_id).json()["messages"]] == [2, 4]

    response = client.put(
        f"/records/{record_id}/messages/{m1['id']}",
        headers=auth_headers(token),
        json={"content": "수정한 첫 답변", "input_revision": 2},
    )
    assert response.status_code == 200
    assert response.json()["input_revision"] == 3
    assert response.json()["message"]["content"] == "수정한 첫 답변"

    detail = _get_record(client, token, record_id).json()
    assert [q["id"] for q in detail["questions"]] == [str(q1)]
    assert [m["id"] for m in detail["messages"]] == [m1["id"]]
    assert detail["messages"][0]["input_revision"] == 3
    assert detail["input_revision"] == 3

    for revision, status in ((2, 409), (3, 404)):
        deleted_edit = client.put(
            f"/records/{record_id}/messages/{m2['id']}",
            headers=auth_headers(token),
            json={"content": "삭제된 답변 수정", "input_revision": revision},
        )
        assert deleted_edit.status_code == status
        if status == 409:
            assert deleted_edit.json()["code"] == "revision_conflict"
            assert deleted_edit.json()["input_revision"] == 3
        else:
            assert deleted_edit.json()["code"] == "not_found"
    assert _get_record(client, token, record_id).json() == detail


def test_same_content_edit_keeps_conversation(
    client,
    user_factory,
    token_for,
    record_factory,
    question_factory,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, _, m1, _, _ = _setup_conversation(
        client, token, record_factory, question_factory, user_id
    )

    response = client.put(
        f"/records/{record_id}/messages/{m1['id']}",
        headers=auth_headers(token),
        json={"content": "첫 답변", "input_revision": 2},
    )
    assert response.status_code == 200
    assert response.json()["input_revision"] == 2

    # Every edit checks the caller's revision first, even when content is unchanged.
    stale = client.put(
        f"/records/{record_id}/messages/{m1['id']}",
        headers=auth_headers(token),
        json={"content": "첫 답변", "input_revision": 1},
    )
    assert stale.status_code == 409

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 2
    assert len(detail["messages"]) == 2
    assert detail["input_revision"] == 2


def test_stale_edit_is_rejected_without_changes(
    client,
    user_factory,
    token_for,
    record_factory,
    question_factory,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, _, m1, _, _ = _setup_conversation(
        client, token, record_factory, question_factory, user_id
    )

    response = client.put(
        f"/records/{record_id}/messages/{m1['id']}",
        headers=auth_headers(token),
        json={"content": "바뀐 답변", "input_revision": 1},
    )
    assert response.status_code == 409
    assert response.json()["input_revision"] == 2

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 2
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["content"] == "첫 답변"


def test_only_user_messages_are_editable(
    client, user_factory, token_for, record_factory, admin
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    with admin.transaction():
        record = admin.execute(
            """
            UPDATE records SET conversation_sequence = conversation_sequence + 1
            WHERE id = %s RETURNING conversation_sequence, input_revision
            """,
            (record_id,),
        ).fetchone()
        assistant_id = uuid4()
        admin.execute(
            """
            INSERT INTO messages
                (id, record_id, question_id, sequence, sender, content,
                 client_message_id, input_revision)
            VALUES (%s, %s, NULL, %s, 'assistant', %s, NULL, %s)
            """,
            (
                assistant_id,
                record_id,
                record["conversation_sequence"],
                "AI 응답",
                record["input_revision"],
            ),
        )

    response = client.put(
        f"/records/{record_id}/messages/{assistant_id}",
        headers=auth_headers(token),
        json={"content": "수정", "input_revision": 0},
    )
    assert response.status_code == 404


def test_other_user_cannot_access_or_modify_record(
    client, user_factory, token_for, record_factory, question_factory
):
    owner_id = user_factory()
    other_id = user_factory()
    owner_token = token_for(owner_id)
    other_token = token_for(other_id)
    record_id = record_factory(owner_id)["record_id"]
    question_id = question_factory(record_id, "질문")

    created = _post_message(
        client,
        owner_token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "question_id": str(question_id),
            "content": "답변",
            "input_revision": 0,
        },
    )
    assert created.status_code == 200
    message_id = created.json()["message"]["id"]

    assert _get_record(client, other_token, record_id).status_code == 404
    assert (
        client.patch(
            f"/records/{record_id}",
            headers=auth_headers(other_token),
            json={"location": "다른 곳"},
        ).status_code
        == 404
    )
    assert (
        _post_message(
            client,
            other_token,
            record_id,
            {
                "client_message_id": str(uuid4()),
                "content": "침입",
                "input_revision": 1,
            },
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/records/{record_id}/messages/{message_id}",
            headers=auth_headers(other_token),
            json={"content": "침입", "input_revision": 1},
        ).status_code
        == 404
    )

    assert (
        client.put(
            f"/records/{record_id}/messages/{uuid4()}",
            headers=auth_headers(owner_token),
            json={"content": "없는 메시지", "input_revision": 1},
        ).status_code
        == 404
    )


def test_get_marks_old_generation_results(
    client, user_factory, token_for, record_factory, admin
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    admin.execute(
        """
        UPDATE records SET
            diagnosis = %s,
            diagnosis_revision = input_revision,
            diagnosis_generation = 1,
            next_question_result = %s,
            next_question_revision = input_revision,
            landlord_draft = '점검 요청문',
            landlord_draft_revision = input_revision,
            landlord_draft_diagnosis_generation = 1,
            provider_draft = '견적 요청문',
            provider_draft_revision = input_revision,
            provider_draft_diagnosis_generation = 0
        WHERE id = %s
        """,
        (
            Jsonb({"severity": "medium"}),
            Jsonb({"ready_for_diagnosis": False}),
            record_id,
        ),
    )

    current = _get_record(client, token, record_id).json()
    assert current["diagnosis"]["is_current"] is True
    assert current["next_question"]["is_current"] is True
    assert current["drafts"]["landlord"]["is_current"] is True
    assert current["drafts"]["provider"]["is_current"] is False

    response = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"symptoms": "새 증상"},
    )
    assert response.status_code == 200

    stale = _get_record(client, token, record_id).json()
    assert stale["input_revision"] == 1
    assert stale["diagnosis"]["is_current"] is False
    assert stale["diagnosis"]["input_revision"] == 0
    assert stale["next_question"]["is_current"] is False
    assert stale["next_question"]["input_revision"] == 0
    assert stale["drafts"]["landlord"]["is_current"] is False
    assert stale["drafts"]["landlord"]["input_revision"] == 0


def test_concurrent_replay_stores_one_message(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(record_id, "질문")
    payload = {
        "client_message_id": str(uuid4()),
        "question_id": str(question_id),
        "content": "동시 답변",
        "input_revision": 0,
    }

    async def send(async_client):
        return await async_client.post(
            f"/records/{record_id}/messages",
            headers=auth_headers(token),
            json=payload,
        )

    responses = _run_concurrently(
        lambda async_client: [send(async_client) for _ in range(8)]
    )
    assert {response.status_code for response in responses} == {200}
    assert len({response.json()["message"]["id"] for response in responses}) == 1

    detail = _get_record(client, token, record_id).json()
    assert len(detail["messages"]) == 1
    assert detail["input_revision"] == 1


def test_concurrent_different_messages_do_not_share_sequences(
    client, user_factory, token_for, record_factory, question_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]
    question_id = question_factory(record_id, "질문")

    async def send(async_client, index):
        return await async_client.post(
            f"/records/{record_id}/messages",
            headers=auth_headers(token),
            json={
                "client_message_id": str(uuid4()),
                "question_id": str(question_id),
                "content": f"동시 답변 {index}",
                "input_revision": 0,
            },
        )

    responses = _run_concurrently(
        lambda async_client: [send(async_client, index) for index in range(8)]
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] + [409] * 7
    for response in responses:
        if response.status_code == 409:
            assert response.json()["input_revision"] == 1

    detail = _get_record(client, token, record_id).json()
    assert len(detail["messages"]) == 1
    assert len({message["sequence"] for message in detail["messages"]}) == 1
    assert detail["input_revision"] == 1


def test_failed_edit_rolls_back_deletions(
    client,
    user_factory,
    token_for,
    record_factory,
    question_factory,
    admin,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, _, m1, _, _ = _setup_conversation(
        client, token, record_factory, question_factory, user_id
    )

    admin.execute(
        """
        CREATE OR REPLACE FUNCTION test_fail_message_update()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'forced test failure';
        END
        $$
        """
    )
    admin.execute(
        """
        CREATE TRIGGER test_fail_message_update
        BEFORE UPDATE ON messages
        FOR EACH ROW EXECUTE FUNCTION test_fail_message_update()
        """
    )
    try:
        response = client.put(
            f"/records/{record_id}/messages/{m1['id']}",
            headers=auth_headers(token),
            json={"content": "실패할 수정", "input_revision": 2},
        )
        assert response.status_code == 500
    finally:
        admin.execute("DROP TRIGGER test_fail_message_update ON messages")
        admin.execute("DROP FUNCTION test_fail_message_update()")

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 2
    assert len(detail["messages"]) == 2
    assert [m["content"] for m in detail["messages"]] == ["첫 답변", "두 번째 답변"]
    assert detail["input_revision"] == 2


def test_message_validation_rejects_unknown_fields(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id = record_factory(user_id)["record_id"]

    response = _post_message(
        client,
        token,
        record_id,
        {
            "client_message_id": str(uuid4()),
            "content": "답변",
            "input_revision": 0,
            "owner_id": str(uuid4()),
        },
    )
    assert response.status_code == 422
