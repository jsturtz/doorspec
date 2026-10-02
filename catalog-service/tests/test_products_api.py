"""HTTP-level tests for /products against a real Postgres test database (see conftest.py)."""

import pytest
from fastapi.testclient import TestClient
from pytest_check import check
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product

PRODUCT = {
    "sku": "LCK-100",
    "category": "lock",
    "manufacturer": "Corbin Russwin",
    "fire_rating_minutes": 90,
    "material": "hollow_metal",
    "electrified": True,
    "voltage": 24,
    "finish": "626",
}

HINGE = {
    "sku": "HNG-200",
    "category": "hinge",
    "manufacturer": "McKinney",
    "fire_rating_minutes": 0,
    "material": "wood",
    "electrified": False,
    "voltage": None,
    "finish": "US26D",
}

MISSING_ID = 999_999


def create(client: TestClient, **overrides) -> dict:
    response = client.post("/products", json={**PRODUCT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


# --- Health ------------------------------------------------------------------


def test_liveness(client):
    assert client.get("/health/").json() == {"status": "healthy"}


def test_readiness_with_database_up(client):
    response = client.get("/health/ready")
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == {"status": "ready"}


# --- POST /products ----------------------------------------------------------


def test_create_returns_201_with_server_assigned_id(client):
    body = create(client)
    with check:
        assert isinstance(body["id"], int)
    with check:
        assert body == {"id": body["id"], **PRODUCT}


def test_create_response_contains_only_contract_fields(client):
    assert set(create(client)) == {"id", *PRODUCT}


def test_create_duplicate_sku_returns_409(client):
    create(client)
    response = client.post("/products", json=PRODUCT)
    with check:
        assert response.status_code == 409
    with check:
        assert "LCK-100" in response.json()["detail"]


def test_create_duplicate_sku_after_whitespace_stripping_returns_409(client):
    create(client)
    response = client.post("/products", json={**PRODUCT, "sku": "  LCK-100  "})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"sku": "lowercase"},
        {"category": "doorknob"},
        {"fire_rating_minutes": 30},
        {"voltage": None},  # electrified without voltage
        {"unexpected": "field"},
    ],
)
def test_create_invalid_body_returns_422(client, overrides):
    response = client.post("/products", json={**PRODUCT, **overrides})
    assert response.status_code == 422


def test_create_invalid_body_writes_nothing(client):
    client.post("/products", json={**PRODUCT, "category": "doorknob"})
    assert client.get("/products").json() == []


# --- GET /products/{id} ------------------------------------------------------


def test_get_returns_product(client):
    created = create(client)
    response = client.get(f"/products/{created['id']}")
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == created


def test_get_missing_returns_404(client):
    response = client.get(f"/products/{MISSING_ID}")
    with check:
        assert response.status_code == 404
    with check:
        assert isinstance(response.json()["detail"], str)


def test_get_non_integer_id_returns_422(client):
    assert client.get("/products/abc").status_code == 422


# --- GET /products -----------------------------------------------------------


def test_list_empty(client):
    response = client.get("/products")
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == []


def test_list_returns_all_ordered_by_id(client):
    first = create(client)
    second = create(client, **HINGE)
    assert [p["id"] for p in client.get("/products").json()] == [first["id"], second["id"]]


def test_list_filters_by_category(client):
    create(client)
    hinge = create(client, **HINGE)
    assert client.get("/products", params={"category": "hinge"}).json() == [hinge]


@pytest.mark.parametrize(
    "fire_rated, expected_skus",
    [("true", ["LCK-100"]), ("false", ["HNG-200"]), (None, ["LCK-100", "HNG-200"])],
)
def test_list_filters_by_fire_rated(client, fire_rated, expected_skus):
    create(client)
    create(client, **HINGE)
    params = {} if fire_rated is None else {"fire_rated": fire_rated}
    assert [p["sku"] for p in client.get("/products", params=params).json()] == expected_skus


def test_list_combines_filters(client):
    create(client)
    create(client, **HINGE)
    params = {"category": "hinge", "fire_rated": "true"}
    assert client.get("/products", params=params).json() == []


@pytest.mark.parametrize(
    "params", [{"category": "doorknob"}, {"fire_rated": "maybe"}, {"category": ""}]
)
def test_list_invalid_filter_returns_422(client, params):
    assert client.get("/products", params=params).status_code == 422


# --- PATCH /products/{id} ----------------------------------------------------


def test_patch_updates_only_sent_fields(client):
    created = create(client)
    response = client.patch(f"/products/{created['id']}", json={"finish": "US32D"})
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == {**created, "finish": "US32D"}


def test_patch_persists(client):
    created = create(client)
    client.patch(f"/products/{created['id']}", json={"finish": "US32D"})
    assert client.get(f"/products/{created['id']}").json()["finish"] == "US32D"


def test_patch_missing_returns_404(client):
    response = client.patch(f"/products/{MISSING_ID}", json={"finish": "US32D"})
    assert response.status_code == 404


def test_patch_sku_to_existing_sku_returns_409(client):
    create(client)
    hinge = create(client, **HINGE)
    response = client.patch(f"/products/{hinge['id']}", json={"sku": "LCK-100"})
    assert response.status_code == 409


def test_patch_electrified_true_uses_stored_voltage_rule(client):
    """Stored product has no voltage, so turning electrified on without one is rejected."""
    hinge = create(client, **HINGE)
    response = client.patch(f"/products/{hinge['id']}", json={"electrified": True})
    assert response.status_code == 422


def test_patch_electrified_true_with_voltage_succeeds(client):
    hinge = create(client, **HINGE)
    response = client.patch(f"/products/{hinge['id']}", json={"electrified": True, "voltage": 12})
    with check:
        assert response.status_code == 200
    with check:
        assert response.json()["voltage"] == 12


def test_patch_electrified_false_while_voltage_stored_returns_422(client):
    """Merged result would be electrified=false with voltage=24: contradictory, so rejected."""
    created = create(client)
    response = client.patch(f"/products/{created['id']}", json={"electrified": False})
    with check:
        assert response.status_code == 422
    with check:
        assert client.get(f"/products/{created['id']}").json()["electrified"] is True


def test_patch_electrified_false_and_clear_voltage_succeeds(client):
    created = create(client)
    response = client.patch(
        f"/products/{created['id']}", json={"electrified": False, "voltage": None}
    )
    with check:
        assert response.status_code == 200
    with check:
        assert response.json()["voltage"] is None


@pytest.mark.parametrize(
    "body", [{"sku": None}, {"sku": "lowercase"}, {"voltage": 99}, {"finsh": "626"}]
)
def test_patch_invalid_body_returns_422(client, body):
    created = create(client)
    response = client.patch(f"/products/{created['id']}", json=body)
    assert response.status_code == 422


def test_patch_empty_body_changes_nothing(client):
    created = create(client)
    response = client.patch(f"/products/{created['id']}", json={})
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == created


# --- PUT /products/{id} ------------------------------------------------------

REPLACEMENT = {
    "sku": "LCK-100-B",
    "category": "exit_device",
    "manufacturer": "Von Duprin",
    "fire_rating_minutes": 180,
    "material": "aluminum",
    "electrified": False,
    "voltage": None,
    "finish": "US32D",
}


def test_put_replaces_every_field(client):
    created = create(client)
    response = client.put(f"/products/{created['id']}", json=REPLACEMENT)
    with check:
        assert response.status_code == 200
    with check:
        assert response.json() == {"id": created["id"], **REPLACEMENT}


def test_put_persists(client):
    created = create(client)
    client.put(f"/products/{created['id']}", json=REPLACEMENT)
    assert client.get(f"/products/{created['id']}").json() == {"id": created["id"], **REPLACEMENT}


def test_put_is_idempotent(client):
    created = create(client)
    first = client.put(f"/products/{created['id']}", json=REPLACEMENT)
    second = client.put(f"/products/{created['id']}", json=REPLACEMENT)
    with check:
        assert second.status_code == 200
    with check:
        assert second.json() == first.json()


def test_put_keeping_own_sku_is_not_a_conflict(client):
    created = create(client)
    response = client.put(f"/products/{created['id']}", json={**PRODUCT, "finish": "US32D"})
    assert response.status_code == 200


def test_put_missing_returns_404(client):
    response = client.put(f"/products/{MISSING_ID}", json=REPLACEMENT)
    with check:
        assert response.status_code == 404
    with check:
        assert isinstance(response.json()["detail"], str)


def test_put_sku_to_existing_sku_returns_409(client):
    create(client)
    hinge = create(client, **HINGE)
    response = client.put(f"/products/{hinge['id']}", json={**HINGE, "sku": "LCK-100"})
    with check:
        assert response.status_code == 409
    with check:
        assert "LCK-100" in response.json()["detail"]


def test_put_partial_body_returns_422(client):
    """Unlike PATCH, PUT is a full replacement: every field is required."""
    created = create(client)
    response = client.put(f"/products/{created['id']}", json={"finish": "US32D"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"voltage": 24},  # not electrified, but has a voltage
        {"electrified": True},  # electrified, no voltage
        {"category": "doorknob"},
        {"unexpected": "field"},
    ],
)
def test_put_invalid_body_returns_422_and_changes_nothing(client, overrides):
    created = create(client)
    response = client.put(f"/products/{created['id']}", json={**REPLACEMENT, **overrides})
    with check:
        assert response.status_code == 422
    with check:
        assert client.get(f"/products/{created['id']}").json() == created


# --- DELETE /products/{id} ---------------------------------------------------


def test_delete_returns_204_and_removes_product(client):
    created = create(client)
    response = client.delete(f"/products/{created['id']}")
    with check:
        assert response.status_code == 204
    with check:
        assert response.content == b""
    with check:
        assert client.get(f"/products/{created['id']}").status_code == 404


def test_delete_missing_returns_404(client):
    assert client.delete(f"/products/{MISSING_ID}").status_code == 404


# --- Database constraints (bypassing the API) --------------------------------


@pytest.mark.parametrize(
    "overrides, constraint",
    [
        ({"category": "doorknob"}, "ck_products_category"),
        ({"material": "steel"}, "ck_products_material"),
        ({"fire_rating_minutes": 30}, "ck_products_fire_rating_minutes"),
        ({"voltage": 99}, "ck_products_voltage_range"),
        ({"voltage": 0}, "ck_products_voltage_range"),
    ],
)
def test_database_rejects_invalid_rows(db_session: Session, overrides, constraint):
    """Defence in depth: the DB enforces the rules even when Pydantic is bypassed."""
    db_session.add(Product(**{**PRODUCT, **overrides}))
    with pytest.raises(IntegrityError, match=constraint):
        db_session.flush()


def test_database_rejects_duplicate_sku(db_session: Session):
    db_session.add(Product(**PRODUCT))
    db_session.flush()
    db_session.add(Product(**{**PRODUCT, "manufacturer": "Other"}))
    with pytest.raises(IntegrityError, match="ix_products_sku"):
        db_session.flush()


def test_tests_are_isolated_from_each_other(client):
    """Every other test created products; each must have been rolled back."""
    assert client.get("/products").json() == []
