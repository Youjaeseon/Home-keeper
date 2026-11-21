from psycopg.types.json import Jsonb

from conftest import auth_headers


def test_record_list_is_own_summaries_in_recent_order(
    client, admin, user_factory, token_for, record_factory
):
    assert client.get("/records").status_code == 401

    user_a = user_factory()
    user_b = user_factory()
    user_c = user_factory()
    token_a = token_for(user_a)
    token_b = token_for(user_b)
    token_c = token_for(user_c)

    first = record_factory(user_a)["record_id"]
    second = record_factory(user_a)["record_id"]
    other = record_factory(user_b)["record_id"]

    assert client.get("/records", headers=auth_headers(token_c)).json() == []

    admin.execute(
        """
        UPDATE records
        SET location = '창가',
            material = '콘크리트',
            symptoms = '검은 얼룩',
            diagnosis = %s,
            updated_at = now() + interval '1 minute'
        WHERE id = %s
        """,
        (
            Jsonb(
                {
                    "suspected_types": ["곰팡이", "결로"],
                    "severity_score": 72,
                    "severity_level": "high",
                }
            ),
            first,
        ),
    )

    response = client.get("/records", headers=auth_headers(token_a))
    assert response.status_code == 200, response.text
    items = response.json()
    assert [item["record_id"] for item in items] == [str(first), str(second)]
    assert set(items[0]) == {
        "record_id",
        "location",
        "material",
        "symptoms",
        "region_id",
        "region_name",
        "suspected_types",
        "severity_score",
        "severity_level",
        "created_at",
        "updated_at",
    }
    assert items[0]["record_id"] == str(first)
    assert items[0]["location"] == "창가"
    assert items[0]["material"] == "콘크리트"
    assert items[0]["symptoms"] == "검은 얼룩"
    assert items[0]["suspected_types"] == ["곰팡이", "결로"]
    assert items[0]["severity_score"] == 72
    assert items[0]["severity_level"] == "high"
    assert items[0]["created_at"]
    assert items[0]["updated_at"]
    assert items[1]["suspected_types"] == []
    assert items[1]["severity_score"] is None
    assert items[1]["severity_level"] is None

    other_items = client.get("/records", headers=auth_headers(token_b)).json()
    assert [item["record_id"] for item in other_items] == [str(other)]
    assert str(first) not in {item["record_id"] for item in other_items}
