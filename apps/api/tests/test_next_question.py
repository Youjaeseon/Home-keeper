import asyncio
import threading
from uuid import uuid4

import httpx

from app.main import app
from conftest import auth_headers

FIRST_QUESTION = "닦은 뒤 같은 흔적이 다시 생겼나요?"
SECOND_QUESTION = "이미 어떤 조치를 했나요?"


def _next_question(client, token, record_id):
    return client.post(
        f"/records/{record_id}/next-question",
        headers=auth_headers(token),
    )


def _get_record(client, token, record_id):
    return client.get(f"/records/{record_id}", headers=auth_headers(token))


def _answer_option(client, token, record_id, question, option_id, revision):
    response = client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(uuid4()),
            "question_id": question["id"],
            "selected_option_id": option_id,
            "input_revision": revision,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _record_with_input(client, token, record_factory, user_id):
    record_id = record_factory(user_id)["record_id"]
    response = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={
            "location": "안방 창틀 아래",
            "symptoms": "검은 곰팡이 의심 얼룩이 번져 있어요",
        },
    )
    assert response.status_code == 200, response.text
    return record_id, response.json()["input_revision"]


def _answer_option(client, token, record_id, question, option_id, revision):
    response = client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(uuid4()),
            "question_id": question["id"],
            "selected_option_id": option_id,
            "input_revision": revision,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_first_question_is_sample_and_stored(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )

    response = _next_question(client, token, record_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "sample"
    assert body["input_revision"] == revision == 1
    assert body["reply"] is None
    assert body["ready_for_diagnosis"] is False
    assert body["question"]["content"] == FIRST_QUESTION
    options = body["question"]["options"]
    assert [option["id"] for option in options] == [
        "recurred",
        "first_seen",
        "unknown",
    ]
    assert len({option["id"] for option in options}) == len(options)
    assert all(option["label"] for option in options)

    detail = _get_record(client, token, record_id).json()
    assert detail["input_revision"] == revision
    assert len(detail["questions"]) == 1
    assert detail["questions"][0]["id"] == body["question"]["id"]
    assert detail["questions"][0]["content"] == FIRST_QUESTION
    assert detail["questions"][0]["answered"] is False
    assert detail["next_question"]["is_current"] is True
    assert detail["next_question"]["result"] == body


def _answer_content(client, token, record_id, question, content, revision):
    response = client.post(
        f"/records/{record_id}/messages",
        headers=auth_headers(token),
        json={
            "client_message_id": str(uuid4()),
            "question_id": question["id"],
            "content": content,
            "input_revision": revision,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _flow_to_second_question(client, token, record_factory, user_id):
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )
    first_response = _next_question(client, token, record_id)
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()
    assert first["question"]["content"] == FIRST_QUESTION

    _answer_option(
        client, token, record_id, first["question"], "recurred", revision
    )
    second_response = _next_question(client, token, record_id)
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    assert second["question"]["content"] == SECOND_QUESTION
    return record_id, first, second


def _flow_to_ready(client, token, record_factory, user_id):
    record_id, first, second = _flow_to_second_question(
        client, token, record_factory, user_id
    )
    _answer_option(
        client, token, record_id, second["question"], "ventilated", 2
    )
    ready_response = _next_question(client, token, record_id)
    assert ready_response.status_code == 200, ready_response.text
    ready = ready_response.json()
    assert ready["ready_for_diagnosis"] is True
    assert ready["question"] is None
    return record_id, first, second, ready


def _run_concurrently(requests):
    async def run():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            return await asyncio.gather(*requests(async_client))

    return asyncio.run(run())


def test_next_question_requires_auth_and_ownership(
    client, user_factory, token_for, record_factory
):
    owner_id = user_factory()
    other_id = user_factory()
    record_id = record_factory(owner_id)["record_id"]
    url = f"/records/{record_id}/next-question"

    assert client.post(url).status_code == 401
    assert (
        client.post(url, headers=auth_headers(token_for(other_id))).status_code
        == 404
    )


def test_selected_option_advances_and_marks_previous_answered(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, first, second = _flow_to_second_question(
        client, token, record_factory, user_id
    )

    assert second["source"] == "sample"
    assert second["input_revision"] == 2
    assert second["ready_for_diagnosis"] is False
    assert second["reply"]
    assert second["question"]["id"] != first["question"]["id"]

    detail = _get_record(client, token, record_id).json()
    assert detail["input_revision"] == 2
    assert [question["answered"] for question in detail["questions"]] == [
        True,
        False,
    ]
    assert [question["input_revision"] for question in detail["questions"]] == [
        1,
        2,
    ]
    assert detail["next_question"]["is_current"] is True
    assert detail["next_question"]["result"] == second

    assistant_messages = [
        message
        for message in detail["messages"]
        if message["sender"] == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["content"] == second["reply"]
    assert assistant_messages[0]["input_revision"] == 2
    assert assistant_messages[0]["question_id"] == first["question"]["id"]


def test_direct_input_rules_advance_to_completion(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )

    first = _next_question(client, token, record_id).json()
    _answer_content(
        client,
        token,
        record_id,
        first["question"],
        "닦아도 다시 나타났어요",
        revision,
    )
    second = _next_question(client, token, record_id).json()
    assert second["question"]["content"] == SECOND_QUESTION

    _answer_content(
        client,
        token,
        record_id,
        second["question"],
        "환기했어요",
        2,
    )
    ready_response = _next_question(client, token, record_id)
    assert ready_response.status_code == 200, ready_response.text
    ready = ready_response.json()
    assert ready["source"] == "sample"
    assert ready["input_revision"] == 3
    assert ready["ready_for_diagnosis"] is True
    assert ready["question"] is None
    assert ready["reply"]

    detail = _get_record(client, token, record_id).json()
    assert [question["answered"] for question in detail["questions"]] == [
        True,
        True,
    ]
    assert detail["input_revision"] == 3
    assert detail["next_question"]["is_current"] is True
    assert detail["next_question"]["result"] == ready


def test_unrelated_message_does_not_complete_question(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )

    first = _next_question(client, token, record_id).json()
    _answer_content(
        client,
        token,
        record_id,
        first["question"],
        "창가에 물이 새요",
        revision,
    )
    response = _next_question(client, token, record_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reply"]
    assert body["question"]["id"] == first["question"]["id"]
    assert body["ready_for_diagnosis"] is False
    assert body["input_revision"] == 2

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 1
    assert detail["questions"][0]["answered"] is False
    assistant_messages = [
        message
        for message in detail["messages"]
        if message["sender"] == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["question_id"] == first["question"]["id"]
    assert detail["next_question"]["is_current"] is True
    assert detail["next_question"]["result"] == body


def test_unknown_answer_is_closed_and_not_reasked(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )

    first = _next_question(client, token, record_id).json()
    _answer_option(
        client, token, record_id, first["question"], "unknown", revision
    )
    second = _next_question(client, token, record_id).json()
    assert second["question"]["content"] == SECOND_QUESTION
    _answer_option(
        client, token, record_id, second["question"], "unknown", 2
    )
    ready = _next_question(client, token, record_id).json()
    assert ready["question"] is None
    assert ready["ready_for_diagnosis"] is True
    assert ready["input_revision"] == 3

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 2
    assert [question["answered"] for question in detail["questions"]] == [
        True,
        True,
    ]
    assert len([message for message in detail["messages"] if message["sender"] == "assistant"]) == 2


def test_same_revision_replay_returns_cached_question_without_generation(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, _ = _record_with_input(client, token, record_factory, user_id)

    first = _next_question(client, token, record_id)
    assert first.status_code == 200
    first_body = first.json()

    def fail(_state):
        raise AssertionError("cached next question must not regenerate")

    monkeypatch.setattr("app.records.build_sample_decision", fail)
    replay = _next_question(client, token, record_id)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first_body

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 1
    assert detail["messages"] == []
    assert detail["input_revision"] == 1


def test_completion_replay_and_null_completion_are_stored_without_regeneration(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    from app.sample_questions import build_sample_decision as real_decision

    user_id = user_factory()
    token = token_for(user_id)
    record_id, _, _, ready = _flow_to_ready(
        client, token, record_factory, user_id
    )

    def fail(_state):
        raise AssertionError("stored next question must not regenerate")

    monkeypatch.setattr("app.records.build_sample_decision", fail)
    replay = _next_question(client, token, record_id)
    assert replay.status_code == 200, replay.text
    assert replay.json() == ready

    monkeypatch.setattr(
        "app.records.build_sample_decision", real_decision
    )
    patched = client.patch(
        f"/records/{record_id}",
        headers=auth_headers(token),
        json={"symptoms": "검은 얼룩이 넓어졌어요"},
    )
    assert patched.status_code == 200
    assert patched.json()["input_revision"] == 4

    completion = _next_question(client, token, record_id)
    assert completion.status_code == 200, completion.text
    null_completion = completion.json()
    assert null_completion["source"] == "sample"
    assert null_completion["input_revision"] == 4
    assert null_completion["reply"] is None
    assert null_completion["question"] is None
    assert null_completion["ready_for_diagnosis"] is True

    monkeypatch.setattr("app.records.build_sample_decision", fail)
    replay_null = _next_question(client, token, record_id)
    assert replay_null.status_code == 200, replay_null.text
    assert replay_null.json() == null_completion

    detail = _get_record(client, token, record_id).json()
    assert detail["input_revision"] == 4
    assert detail["next_question"]["is_current"] is True
    assert detail["next_question"]["result"] == null_completion
    assert [question["answered"] for question in detail["questions"]] == [
        True,
        True,
    ]


def test_concurrent_requests_store_one_question_and_one_reply(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    from app.sample_questions import build_sample_decision as real_decision

    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )
    first = _next_question(client, token, record_id).json()
    _answer_option(
        client, token, record_id, first["question"], "recurred", revision
    )

    barrier = threading.Barrier(2, timeout=10)

    def synchronized(state):
        barrier.wait()
        return real_decision(state)

    monkeypatch.setattr("app.records.build_sample_decision", synchronized)

    async def send(async_client):
        return await async_client.post(
            f"/records/{record_id}/next-question",
            headers=auth_headers(token),
        )

    responses = _run_concurrently(
        lambda async_client: [send(async_client) for _ in range(2)]
    )
    assert {response.status_code for response in responses} == {200}
    bodies = [response.json() for response in responses]
    assert bodies[0] == bodies[1]
    assert bodies[0]["question"]["content"] == SECOND_QUESTION

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 2
    assert len(detail["messages"]) == 2
    assert (
        len(
            [
                message
                for message in detail["messages"]
                if message["sender"] == "assistant"
            ]
        )
        == 1
    )
    assert detail["next_question"]["result"] == bodies[0]


def test_input_change_during_generation_returns_409_without_partial_save(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    from app.sample_questions import build_sample_decision as real_decision

    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )
    first = _next_question(client, token, record_id).json()
    _answer_option(
        client, token, record_id, first["question"], "recurred", revision
    )

    started = threading.Event()
    release = threading.Event()

    def slow(state):
        started.set()
        if not release.wait(10):
            raise AssertionError("test did not release the generator")
        return real_decision(state)

    monkeypatch.setattr("app.records.build_sample_decision", slow)

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            pending = asyncio.create_task(
                async_client.post(
                    f"/records/{record_id}/next-question",
                    headers=auth_headers(token),
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 10)
                patched = await async_client.patch(
                    f"/records/{record_id}",
                    headers=auth_headers(token),
                    json={"symptoms": "새로 번진 얼룩"},
                )
                assert patched.status_code == 200, patched.text
                assert patched.json()["input_revision"] == 3
            finally:
                release.set()
            response = await pending
            return response

    response = asyncio.run(scenario())
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "revision_conflict"
    assert response.json()["input_revision"] == 3

    detail = _get_record(client, token, record_id).json()
    assert len(detail["questions"]) == 1
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["sender"] == "user"
    assert detail["input_revision"] == 3
    assert detail["next_question"]["input_revision"] == 1
    assert detail["next_question"]["is_current"] is False


def test_generation_failure_saves_nothing(
    client,
    user_factory,
    token_for,
    record_factory,
    monkeypatch,
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, revision = _record_with_input(
        client, token, record_factory, user_id
    )

    def fail(_state):
        raise RuntimeError("sample generation failed")

    monkeypatch.setattr("app.records.build_sample_decision", fail)
    response = _next_question(client, token, record_id)
    assert response.status_code == 500

    detail = _get_record(client, token, record_id).json()
    assert detail["questions"] == []
    assert detail["messages"] == []
    assert detail["next_question"] is None
    assert detail["input_revision"] == revision == 1


def _get_first_user_message(detail, first_question):
    return next(
        message
        for message in detail["messages"]
        if message["sender"] == "user"
        and message["question_id"] == first_question["id"]
    )


def test_editing_past_answer_reasks_without_stale_question_or_cache(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, first, second = _flow_to_second_question(
        client, token, record_factory, user_id
    )
    old_second_id = second["question"]["id"]
    detail = _get_record(client, token, record_id).json()
    first_message = _get_first_user_message(detail, first["question"])

    edited = client.put(
        f"/records/{record_id}/messages/{first_message['id']}",
        headers=auth_headers(token),
        json={"content": "창가에 물이 새요", "input_revision": 2},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["input_revision"] == 3

    after_edit = _get_record(client, token, record_id).json()
    assert [question["id"] for question in after_edit["questions"]] == [
        first["question"]["id"]
    ]
    assert after_edit["questions"][0]["answered"] is False
    assert len(after_edit["messages"]) == 1
    assert after_edit["next_question"] is None
    assert old_second_id not in [
        question["id"] for question in after_edit["questions"]
    ]

    response = _next_question(client, token, record_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["question"]["id"] == first["question"]["id"]
    assert body["question"]["content"] == FIRST_QUESTION
    assert body["ready_for_diagnosis"] is False
    assert body["reply"]
    assert old_second_id not in str(body)

    detail = _get_record(client, token, record_id).json()
    assert [question["id"] for question in detail["questions"]] == [
        first["question"]["id"]
    ]
    assert detail["questions"][0]["answered"] is False
    assert detail["next_question"]["is_current"] is True


def test_editing_past_answer_relevant_rebuilds_second_question_with_new_id(
    client, user_factory, token_for, record_factory
):
    user_id = user_factory()
    token = token_for(user_id)
    record_id, first, second = _flow_to_second_question(
        client, token, record_factory, user_id
    )
    old_second_id = second["question"]["id"]
    detail = _get_record(client, token, record_id).json()
    first_message = _get_first_user_message(detail, first["question"])

    edited = client.put(
        f"/records/{record_id}/messages/{first_message['id']}",
        headers=auth_headers(token),
        json={"content": "처음 발견했어요", "input_revision": 2},
    )
    assert edited.status_code == 200, edited.text

    response = _next_question(client, token, record_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["question"]["content"] == SECOND_QUESTION
    assert body["question"]["id"] != old_second_id
    assert body["ready_for_diagnosis"] is False

    detail = _get_record(client, token, record_id).json()
    assert [question["answered"] for question in detail["questions"]] == [
        True,
        False,
    ]
    assert old_second_id not in [
        question["id"] for question in detail["questions"]
    ]
    assert detail["next_question"]["result"] == body


def test_openapi_marks_next_question_source_as_sample(client):
    spec = client.get("/openapi.json").json()
    source = spec["components"]["schemas"]["NextQuestionResponse"]["properties"][
        "source"
    ]
    assert "샘플" in source["description"]
    assert "sample" in source["description"]

