"""Requester-provider 1:1 chat rooms (REST).

Rooms are unique per (requester, provider) via a DB constraint, so concurrent
creates converge on one room. A requester shares a server-built defect summary
snapshot; providers never get access to the source record or the profile.
"""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Path, Query
from psycopg.types.json import Jsonb

from app.auth import get_current_user
from app.db import read_transaction, transaction
from app.errors import chat_message_conflict, invalid_request, not_found
from app.schemas import (
    ChatMessageCreateRequest,
    ChatMessageListResponse,
    ChatMessageOut,
    ChatRoomCreateRequest,
    ChatRoomListItem,
    ChatRoomOut,
    ErrorResponse,
)

MAX_MESSAGE_LENGTH = 2000
PREVIEW_LENGTH = 80

_MESSAGE_COLUMNS = """
    id AS message_id, room_id, sender_id, sender_role, message_type,
    record_id, content, payload, client_message_id, created_at
"""

_ROOM_COLUMNS = """
    r.id AS room_id, r.requester_id, r.provider_id, r.latest_record_id,
    r.last_message_at, r.created_at, r.updated_at, p.name AS provider_name
"""


def _error_response(
    model: type[ErrorResponse],
    description: str,
    examples: dict[str, dict],
) -> dict:
    return {
        "model": model,
        "description": description,
        "content": {"application/json": {"examples": examples}},
    }


_UNAUTHORIZED_RESPONSE = _error_response(
    ErrorResponse,
    "인증 실패 또는 만료",
    {
        "unauthorized": {
            "summary": "유효하지 않거나 누락된 액세스 토큰",
            "value": {
                "code": "unauthorized",
                "message": "액세스 토큰이 유효하지 않거나 만료되었습니다.",
            },
        }
    },
)

_NOT_FOUND_RESPONSE = _error_response(
    ErrorResponse,
    "채팅방·기록·업체를 찾을 수 없거나 참여자가 아님",
    {
        "room_not_found": {
            "summary": "채팅방 없음 또는 참여자 아님",
            "value": {"code": "not_found", "message": "채팅방을 찾을 수 없습니다."},
        },
        "record_not_found": {
            "summary": "기록 없음 또는 다른 사용자의 기록",
            "value": {"code": "not_found", "message": "기록을 찾을 수 없습니다."},
        },
        "provider_not_found": {
            "summary": "업체 없음(샘플 업체 포함)",
            "value": {"code": "not_found", "message": "업체를 찾을 수 없습니다."},
        },
    },
)

_VALIDATION_ERROR_RESPONSE = _error_response(
    ErrorResponse,
    "요청 형식 오류 또는 채팅할 수 없는 업체",
    {
        "invalid_request": {
            "summary": "요청 스키마 검증 실패 또는 채팅 불가 업체",
            "value": {
                "code": "invalid_request",
                "message": "이 업체는 앱 채팅을 사용할 수 없습니다.",
            },
        }
    },
)

_MESSAGE_CONFLICT_RESPONSE = _error_response(
    ErrorResponse,
    "같은 `client_message_id`로 다른 내용 전송",
    {
        "message_conflict": {
            "summary": "동일 메시지 ID 내용 충돌",
            "value": {
                "code": "message_conflict",
                "message": "같은 메시지 ID로 다른 내용이 이미 저장되었습니다.",
            },
        }
    },
)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: _UNAUTHORIZED_RESPONSE},
)


def _room_for_user(conn, room_id: UUID, user_id: UUID, *, lock: bool = False) -> dict:
    row = conn.execute(
        f"""
        SELECT {_ROOM_COLUMNS}, p.account_user_id AS provider_user_id
        FROM chat_rooms r
        JOIN providers p ON p.id = r.provider_id
        WHERE r.id = %s AND (r.requester_id = %s OR p.account_user_id = %s)
        {"FOR UPDATE OF r" if lock else ""}
        """,
        (room_id, user_id, user_id),
    ).fetchone()
    if row is None:
        raise not_found("채팅방을 찾을 수 없습니다.")
    return row


def _summary_message(record: dict) -> tuple[str, dict]:
    diagnosis = record["diagnosis"] if isinstance(record["diagnosis"], dict) else {}
    suspected = diagnosis.get("suspected_types")
    causes = diagnosis.get("causes")
    score = diagnosis.get("severity_score")
    payload = {
        "record_id": str(record["id"]),
        "location": record["location"],
        "material": record["material"],
        "symptoms": record["symptoms"],
        "suspected_types": suspected if isinstance(suspected, list) else [],
        "severity_score": score if isinstance(score, int) else None,
        "severity_level": diagnosis.get("severity_level"),
        "causes": causes if isinstance(causes, list) else [],
        "diagnosis_source": diagnosis.get("source"),
        "input_revision": record["input_revision"],
        "diagnosis_generation": record["diagnosis_generation"],
    }
    content = "\n".join(
        [
            "[하자 분석 요약]",
            f"위치: {record['location'] or '미입력'}",
            f"재질: {record['material'] or '미입력'}",
            f"증상: {record['symptoms'] or '미입력'}",
            f"의심 유형: {', '.join(payload['suspected_types']) or '미확인'}",
            f"심각도: {f'{score}%' if payload['severity_score'] is not None else '판단 보류'}",
            f"추정 원인: {'; '.join(payload['causes']) or '미확인'}",
        ]
    )
    return content, payload


@router.get(
    "/rooms",
    response_model=list[ChatRoomListItem],
    summary="내 채팅방 목록",
    description=(
        "로그인한 요청인 또는 연결된 업체 계정이 참여 중인 채팅방을 최근 메시지 시각 내림차순으로 반환합니다.\n\n"
        "- `counterpart_name`은 상대방 이름입니다(요청인에게는 업체명, 업체에게는 요청인 닉네임, 프로필이 없으면 `요청인`).\n"
        "- `last_message_preview`는 최근 메시지 본문의 앞 80자입니다. 메시지가 없으면 `null`입니다.\n"
        "- 실시간 수신 방식은 아직 미확정입니다. 앱은 이 목록과 메시지 이력을 짧은 주기로 다시 조회해 갱신할 수 있습니다."
    ),
    response_description="참여 중인 채팅방 목록",
)
def list_rooms(user_id: UUID = Depends(get_current_user)):
    with read_transaction() as conn:
        rows = conn.execute(
            f"""
            SELECT
                {_ROOM_COLUMNS},
                pr.nickname AS requester_nickname,
                last.content AS last_message_content
            FROM chat_rooms r
            JOIN providers p ON p.id = r.provider_id
            LEFT JOIN profiles pr ON pr.user_id = r.requester_id
            LEFT JOIN LATERAL (
                SELECT content FROM chat_messages m
                WHERE m.room_id = r.id
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT 1
            ) last ON TRUE
            WHERE r.requester_id = %s OR p.account_user_id = %s
            ORDER BY COALESCE(r.last_message_at, r.created_at) DESC, r.id DESC
            """,
            (user_id, user_id),
        ).fetchall()

    return [
        {
            **{key: row[key] for key in (
                "room_id", "requester_id", "provider_id", "provider_name",
                "latest_record_id", "last_message_at", "created_at", "updated_at",
            )},
            "counterpart_name": (
                row["provider_name"]
                if row["requester_id"] == user_id
                else row["requester_nickname"] or "요청인"
            ),
            "last_message_preview": (
                row["last_message_content"][:PREVIEW_LENGTH]
                if row["last_message_content"] is not None
                else None
            ),
        }
        for row in rows
    ]


@router.post(
    "/rooms",
    response_model=ChatRoomOut,
    summary="채팅방 생성 또는 재사용",
    description=(
        "요청인이 채팅 가능한 실제 업체를 지정해 1:1 채팅방을 만들거나 기존 방을 재사용합니다.\n\n"
        "- `(requester_id, provider_id)` 유일 제약으로 동시 요청에도 방이 하나만 생깁니다.\n"
        "- `record_id`를 보내면 서버가 저장된 기록·진단으로 하자 요약을 만들어 `record_summary` 메시지로 공유합니다. "
        "클라이언트가 보낸 요약은 받지 않으며, 같은 방에 같은 기록·같은 요약이 이미 있으면 다시 공유하지 않습니다.\n"
        "- 공유 요약에는 하자 입력과 진단 결과만 담고 등록 주소·이메일·닉네임·원본 사진은 담지 않습니다.\n"
        "- 샘플 업체(`is_sample=true`)는 DB에 없으므로 `404`, 계정이 연결되지 않은 업체는 `422`입니다. 업체 계정은 방을 만들 수 없습니다."
    ),
    response_description="생성 또는 재사용된 채팅방",
    responses={
        404: _NOT_FOUND_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def create_room(
    body: Annotated[
        ChatRoomCreateRequest,
        Body(
            openapi_examples={
                "share_record": {
                    "summary": "하자 기록을 공유하며 채팅 시작",
                    "value": {
                        "provider_id": "7a1d4c1e-6f0b-4a8e-9c3d-2b5e6f7a8b9c",
                        "record_id": "550e8400-e29b-41d4-a716-446655440000",
                    },
                },
                "room_only": {
                    "summary": "기록 없이 채팅방만 열기",
                    "value": {"provider_id": "7a1d4c1e-6f0b-4a8e-9c3d-2b5e6f7a8b9c"},
                },
            }
        ),
    ],
    user_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        if conn.execute(
            "SELECT 1 FROM providers WHERE account_user_id = %s", (user_id,)
        ).fetchone():
            raise invalid_request("업체 계정은 채팅방을 만들 수 없습니다.")

        provider = conn.execute(
            "SELECT id, name, account_user_id FROM providers WHERE id = %s",
            (body.provider_id,),
        ).fetchone()
        if provider is None:
            raise not_found("업체를 찾을 수 없습니다.")
        if provider["account_user_id"] is None:
            raise invalid_request("이 업체는 앱 채팅을 사용할 수 없습니다.")

        record = None
        if body.record_id is not None:
            record = conn.execute(
                "SELECT * FROM records WHERE id = %s AND owner_id = %s",
                (body.record_id, user_id),
            ).fetchone()
            if record is None:
                raise not_found("기록을 찾을 수 없습니다.")

        room = conn.execute(
            """
            INSERT INTO chat_rooms (requester_id, provider_id, latest_record_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (requester_id, provider_id) DO UPDATE
            SET latest_record_id = COALESCE(EXCLUDED.latest_record_id, chat_rooms.latest_record_id)
            RETURNING id AS room_id, requester_id, provider_id, latest_record_id,
                      last_message_at, created_at, updated_at
            """,
            (user_id, provider["id"], body.record_id),
        ).fetchone()

        if record is not None:
            content, payload = _summary_message(record)
            duplicate = conn.execute(
                """
                SELECT 1 FROM chat_messages
                WHERE room_id = %s AND message_type = 'record_summary'
                  AND record_id = %s AND payload = %s
                """,
                (room["room_id"], record["id"], Jsonb(payload)),
            ).fetchone()
            if duplicate is None:
                message = conn.execute(
                    """
                    INSERT INTO chat_messages
                        (room_id, sender_id, sender_role, message_type, record_id,
                         content, payload, client_message_id)
                    VALUES (%s, %s, 'requester', 'record_summary', %s, %s, %s, %s)
                    RETURNING created_at
                    """,
                    (
                        room["room_id"],
                        user_id,
                        record["id"],
                        content,
                        Jsonb(payload),
                        uuid4(),
                    ),
                ).fetchone()
                conn.execute(
                    """
                    UPDATE chat_rooms
                    SET last_message_at = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (message["created_at"], room["room_id"]),
                )
                room = conn.execute(
                    f"SELECT {_ROOM_COLUMNS} FROM chat_rooms r "
                    "JOIN providers p ON p.id = r.provider_id WHERE r.id = %s",
                    (room["room_id"],),
                ).fetchone()

    return {**room, "provider_name": provider["name"]}


@router.get(
    "/rooms/{room_id}/messages",
    response_model=ChatMessageListResponse,
    summary="채팅 메시지 이력 조회",
    description=(
        "참여자(요청인 본인 또는 해당 업체 연결 계정)에게만 메시지 이력을 반환합니다.\n\n"
        "- 정렬은 `created_at`, `id` 오름차순입니다.\n"
        "- `limit`(기본 50, 최대 100)과 `offset`으로 페이지를 나눕니다. `has_more=true`면 같은 조건에 `offset + limit`으로 다음 페이지를 요청합니다.\n"
        "- 반복 조회(폴링)는 `GET /chat/rooms`의 `last_message_at`이 바뀌었는지 확인한 뒤, 마지막으로 받은 개수만큼 `offset`을 늘려 새 메시지를 가져오는 방식으로 사용합니다. "
        "메시지는 수정·삭제되지 않으므로 `offset`이 안정적입니다."
    ),
    response_description="시간순 채팅 메시지 페이지",
    responses={404: _NOT_FOUND_RESPONSE, 422: _VALIDATION_ERROR_RESPONSE},
)
def list_messages(
    room_id: Annotated[UUID, Path(description="채팅방 UUID.")],
    limit: Annotated[int, Query(ge=1, le=100, description="페이지 크기. 기본 50, 최대 100.")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 메시지 수. 기본 0.")] = 0,
    user_id: UUID = Depends(get_current_user),
):
    with read_transaction() as conn:
        _room_for_user(conn, room_id, user_id)
        rows = conn.execute(
            f"""
            SELECT {_MESSAGE_COLUMNS} FROM chat_messages
            WHERE room_id = %s
            ORDER BY created_at, id
            LIMIT %s OFFSET %s
            """,
            (room_id, limit + 1, offset),
        ).fetchall()

    return {
        "messages": rows[:limit],
        "limit": limit,
        "offset": offset,
        "has_more": len(rows) > limit,
    }


@router.post(
    "/rooms/{room_id}/messages",
    response_model=ChatMessageOut,
    summary="채팅 메시지 전송",
    description=(
        "참여자가 보낸 메시지를 저장합니다. 발신자 ID와 역할은 액세스 토큰과 방 참여 정보에서 결정하며 요청 본문의 사용자 ID·역할은 받지 않습니다.\n\n"
        "- `content`는 공백만 불가하며 최대 2000자입니다.\n"
        "- 같은 `client_message_id`와 같은 내용을 다시 보내면 기존 메시지를 반환합니다(멱등). 같은 ID에 다른 내용을 보내면 `409`(`message_conflict`)입니다.\n"
        "- 다른 참여자의 방, 다른 업체, 비참여자는 `404`입니다."
    ),
    response_description="저장되었거나 재전송으로 반환된 메시지",
    responses={
        404: _NOT_FOUND_RESPONSE,
        409: _MESSAGE_CONFLICT_RESPONSE,
        422: _VALIDATION_ERROR_RESPONSE,
    },
)
def create_message(
    room_id: Annotated[UUID, Path(description="메시지를 보낼 채팅방 UUID.")],
    body: Annotated[
        ChatMessageCreateRequest,
        Body(
            openapi_examples={
                "text_message": {
                    "summary": "텍스트 메시지 전송",
                    "value": {
                        "client_message_id": "8a5f2f4e-2c1b-4a3a-9b8e-1d2f3a4b5c6d",
                        "content": "내일 오후에 방문 점검 가능할까요?",
                    },
                }
            }
        ),
    ],
    user_id: UUID = Depends(get_current_user),
):
    with transaction() as conn:
        room = _room_for_user(conn, room_id, user_id, lock=True)
        sender_role = (
            "requester" if room["requester_id"] == user_id else "provider"
        )

        inserted = conn.execute(
            f"""
            INSERT INTO chat_messages
                (room_id, sender_id, sender_role, message_type, content, client_message_id)
            VALUES (%s, %s, %s, 'text', %s, %s)
            ON CONFLICT (room_id, client_message_id) DO NOTHING
            RETURNING {_MESSAGE_COLUMNS}
            """,
            (room_id, user_id, sender_role, body.content, body.client_message_id),
        ).fetchone()

        if inserted is None:
            existing = conn.execute(
                f"""
                SELECT {_MESSAGE_COLUMNS} FROM chat_messages
                WHERE room_id = %s AND client_message_id = %s
                """,
                (room_id, body.client_message_id),
            ).fetchone()
            if (
                existing is None
                or existing["sender_id"] != user_id
                or existing["message_type"] != "text"
                or existing["content"] != body.content
            ):
                raise chat_message_conflict()
            return existing

        conn.execute(
            "UPDATE chat_rooms SET last_message_at = %s, updated_at = now() WHERE id = %s",
            (inserted["created_at"], room_id),
        )

    return inserted
