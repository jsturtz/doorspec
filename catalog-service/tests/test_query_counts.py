"""Guards against N+1 queries: the query count must not grow with the number of rows returned."""

import pytest
from pytest_check import check

from tests.test_products_api import PRODUCT

CERTIFICATIONS = [{"standard": "UL 10C"}, {"standard": "ANSI/BHMA A156.13 Grade 1"}]


def seed(client, count: int) -> list[dict]:
    created = []
    for i in range(count):
        body = {**PRODUCT, "sku": f"QC-{i:03d}", "certifications": CERTIFICATIONS}
        response = client.post("/products", json=body)
        assert response.status_code == 201, response.text
        created.append(response.json())
    return created


@pytest.fixture
def fresh_session(db_session):
    """Empty the identity map, like a new request in production.

    Tests share one session, so objects created earlier stay loaded with their relationships,
    which would hide lazy loads and make an N+1 bug pass.
    """

    def clear() -> None:
        db_session.expunge_all()

    return clear


@pytest.mark.parametrize("count", [5, 20])
def test_list_query_count_is_constant(client, query_counter, fresh_session, count):
    seed(client, count)
    fresh_session()
    query_counter.statements.clear()

    items = client.get("/products", params={"limit": count}).json()["items"]

    with check:
        assert len(items) == count
    with check:
        assert all(len(item["certifications"]) == 2 for item in items)
    with check:  # products + certifications, regardless of count (lazy loading would be 1 + count)
        assert len(query_counter.selects) == 2, query_counter.selects


def test_get_by_id_query_count(client, query_counter, fresh_session):
    product_id = seed(client, 1)[0]["id"]
    fresh_session()
    query_counter.statements.clear()

    client.get(f"/products/{product_id}")

    assert len(query_counter.selects) == 2, query_counter.selects
