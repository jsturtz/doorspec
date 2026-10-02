# Design Decisions

A running log of the significant design choices in DoorSpec: what was decided, what else was considered, and why. Each entry is a lightweight [Architecture Decision Record](https://adr.github.io/). New decisions are added at the end; superseded ones are marked, not deleted.

| # | Decision | Area |
|---|---|---|
| 1 | [Monorepo with one independent project per service](#1-monorepo-with-one-independent-project-per-service) | Structure |
| 2 | [API schemas are separate from ORM models](#2-api-schemas-are-separate-from-orm-models) | API design |
| 3 | [Shared vocabulary lives in a dependency-free domain module](#3-shared-vocabulary-lives-in-a-dependency-free-domain-module) | Structure |
| 4 | [Validate at the API edge and enforce in the database](#4-validate-at-the-api-edge-and-enforce-in-the-database) | Data integrity |
| 5 | [Enums stored as VARCHAR + CHECK, not native Postgres ENUM](#5-enums-stored-as-varchar--check-not-native-postgres-enum) | Database |
| 6 | [PATCH distinguishes omitted fields from explicit nulls](#6-patch-distinguishes-omitted-fields-from-explicit-nulls) | API design |
| 7 | [Configuration from the environment, one `.env` per service](#7-configuration-from-the-environment-one-env-per-service) | Config |
| 8 | [Separate liveness and readiness endpoints](#8-separate-liveness-and-readiness-endpoints) | Operations |
| 9 | [Schema changes through Alembic migrations, run as a deploy step](#9-schema-changes-through-alembic-migrations-run-as-a-deploy-step) | Database |
| 10 | [Deterministic constraint names](#10-deterministic-constraint-names) | Database |
| 11 | [Synchronous SQLAlchemy with sync route handlers](#11-synchronous-sqlalchemy-with-sync-route-handlers) | Performance |
| 12 | [API tests run against real Postgres, rolled back per test](#12-api-tests-run-against-real-postgres-rolled-back-per-test) | Testing |

---

## 1. Monorepo with one independent project per service

**Context:** DoorSpec will grow to several services (catalog, rules, spec, auth) that need to deploy independently.

**Decision:** One repository, with each service as its own self-contained `uv` project (its own `pyproject.toml`, lockfile, virtualenv, `.env`, and migrations). Shared tooling (ruff, pre-commit, Docker Compose) lives at the root.

**Why:** Services can't accidentally import each other's code, and each can be built and deployed alone, while one clone still gives a developer the whole system and consistent lint rules.

**Trade-off:** Some duplication between services (each has its own `db.py`, config, etc.). That's deliberate; sharing it through a common library would couple their release cycles.

## 2. API schemas are separate from ORM models

**Context:** A product has a storage shape (table, columns) and an API shape (what clients send and receive). One class could serve both, e.g. with SQLModel.

**Decision:** Pydantic schemas (`schemas.py`) define the API contract; SQLAlchemy models (`models.py`) define storage. Each resource has `Base` / `Create` / `Read` / `Update` schemas: `Create` and `Read` are siblings under a field-only `Base`, and `Update` is separate because every field is optional.

**Why:** The database can change (renamed columns, split tables, internal-only fields) without breaking clients, and internal columns can never leak into responses by accident. Input rules live only on input schemas, so a rule added later never turns a `GET` on older data into a 500.

**Trade-off:** More classes, and two definitions to keep aligned. Mitigated by decision 3 and by tests that validate a real model instance through the `Read` schema.

## 3. Shared vocabulary lives in a dependency-free domain module

**Context:** Enums (category, material, fire rating) and limits (SKU length, voltage range) are needed by both schemas and models.

**Decision:** `app/domain.py` holds them and imports neither Pydantic nor SQLAlchemy. Models and schemas both import from it, and never from each other.

**Why:** One definition per rule means the API limit and the column limit can't drift apart, and the dependency direction keeps storage and contract decoupled.

## 4. Validate at the API edge and enforce in the database

**Decision:** Pydantic rejects invalid input with a descriptive `422` before it reaches business logic. The database independently enforces the same invariants: `NOT NULL`, column lengths, `CHECK` constraints, and a unique index on SKU.

**Why:** The API gives clients precise, field-level errors. The database guarantees integrity for data that arrives any other way (scripts, manual fixes, future bugs). Unknown fields are rejected (`extra="forbid"`) instead of silently ignored, which also blocks mass assignment.

## 5. Enums stored as VARCHAR + CHECK, not native Postgres ENUM

**Context:** Category and material must be enforced by the database. The options are a native Postgres `ENUM` type, a `VARCHAR` with a `CHECK` constraint, or an unconstrained string.

**Decision:** `VARCHAR` + `CHECK (... IN (...))` for category and material. Fire rating is an `INTEGER` + `CHECK`. Values are stored as the enum *values* (`exit_device`), matching the API, not SQLAlchemy's default of member names (`EXIT_DEVICE`).

**Why:** It's still enforced by the database, without the operational cost of a native `ENUM`: its values can't easily be removed or renamed, Alembic autogenerate doesn't detect added values, and the type is left behind on downgrade. Fire rating stays numeric so rules can compare it (`>= 60`).

**Trade-off:** Changing the allowed values still needs a migration, but it's a plain constraint swap.

## 6. PATCH distinguishes omitted fields from explicit nulls

**Decision:** In a `PATCH` body, an omitted field means "leave unchanged" and `null` means "clear". Only nullable fields (`voltage`) accept `null`; `{"sku": null}` is a `422`. Only fields the client actually sent are applied (`model_dump(exclude_unset=True)`).

**Why:** Without this, a client can't tell the API "don't touch this" apart from "remove this", and a `null` on a required field would only fail at the database as a 500.

**Consequence:** Cross-field rules (an electrified product needs a voltage) can't be checked on a partial body. They're checked on the stored product with the patch merged in.

**PUT as well:** `PUT` is also offered for full replacement (every field required, idempotent). PATCH is the primary update path because it sends only what changed, which avoids the lost-update problem where a full-object write overwrites someone else's concurrent change with stale values.

## 7. Configuration from the environment, one `.env` per service

**Decision:** Each service reads typed settings with `pydantic-settings`, in this order: environment variables, then the service's own `.env` (gitignored, with a committed `.env.example`). Settings are validated at startup and cached.

**Why:** The same image runs locally, in CI, and in the cloud ([12-factor config](https://12factor.net/config)), with no secrets in git. Missing or invalid config fails at startup, not on the first request. Per-service files mirror how containers receive their environment and keep each service's secrets to itself.

## 8. Separate liveness and readiness endpoints

**Decision:** `GET /health` (liveness) only confirms the process is up. `GET /health/ready` (readiness) runs `SELECT 1` and returns `503` if the database is unreachable.

**Why:** Orchestrators handle them differently: failed liveness restarts the container, while failed readiness only stops routing traffic to it. A database outage should take instances out of rotation, not trigger a restart loop. Only connection errors map to `503`; anything else surfaces as a 500, so bugs aren't disguised as outages.

## 9. Schema changes through Alembic migrations, run as a deploy step

**Decision:** Every schema change is a reviewed, versioned Alembic migration committed alongside the model change. In deployed environments, migrations run once as a pipeline step before the new version rolls out, never at application startup. Autogenerated migrations are always read and hand-corrected (for example, renames are detected as drop + add).

**Why:** `create_all()` can't evolve a table that already holds data. Running migrations at startup races when several replicas boot at once. Schema changes that must coexist with the previous release use expand → migrate → contract.

## 10. Deterministic constraint names

**Decision:** `Base.metadata` uses a naming convention (`pk_products`, `ix_products_sku`, `ck_products_voltage_range`, ...).

**Why:** Without one, Postgres generates names, and a later migration that drops or alters a constraint can't reliably refer to it.

## 11. Synchronous SQLAlchemy with sync route handlers

**Decision:** catalog-service uses a synchronous SQLAlchemy engine, and its database-backed routes are plain `def`, which FastAPI runs in a threadpool.

**Why:** It's simpler, and the threadpool handles the expected load. The rule that matters is never making a blocking database call inside `async def`, because that stalls the event loop for every request. Async I/O will be used where it pays off: concurrent outbound HTTP between services.

## 12. API tests run against real Postgres, rolled back per test

**Context:** Endpoint tests need a database. Common shortcuts are in-memory SQLite or rebuilding the schema with `create_all()`.

**Decision:** Tests use a dedicated `<db>_test` database on the real Postgres server, built by running the actual Alembic migrations (`downgrade base`, then `upgrade head`) once per test session. Each test runs inside an outer transaction, with the session in savepoint mode, so route code calls `commit()` normally and everything is rolled back afterwards. The app's `get_db` dependency is overridden to use that session. `DATABASE_URL` is pointed at the test database before the app is imported, so a test run can't touch development data.

**Why:** SQLite would hide exactly what needs testing: it ignores `VARCHAR` lengths, reports constraint violations differently (so the 409 path couldn't be tested), and handles CHECK constraints and transactions differently. Building the schema from migrations means every test run also verifies the migrations. Per-test rollback keeps tests isolated and fast (the full suite runs in under a second) without recreating the database.

**Trade-off:** Tests need the database container running.
