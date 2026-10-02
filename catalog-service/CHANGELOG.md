# Changelog: catalog-service

All notable changes to catalog-service's API and behaviour. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the service uses [Semantic Versioning](https://semver.org/). See the [versioning policy](../docs/decisions.md#14-api-versioning-and-breaking-change-policy).

## [0.2.0] - 2026-10-02

### Changed
- **BREAKING:** `GET /products` now returns a page envelope instead of a bare JSON array:
  ```json
  { "items": [ ... ], "next_cursor": "eyJpZCI6NDB9" }
  ```
  **Migration:** read products from `items`. To fetch everything, repeat the request with `cursor=<next_cursor>` until `next_cursor` is `null`. Keep the same filters on every page.
- `GET /products` returns at most 20 products by default. Before, it returned every product.

### Added
- Cursor (keyset) pagination on `GET /products`:
  - `limit`: page size, 1 to 100, default 20
  - `cursor`: an opaque token from the previous page's `next_cursor`. Clients must not parse or construct it.
- `400 Bad Request` for a malformed or tampered `cursor`.
- The API version now appears in the OpenAPI spec (`info.version`).

## [0.1.0] - 2026-10-02

### Added
- Product catalog CRUD: `POST /products`, `GET /products` (filter by `category`, `fire_rated`), `GET /products/{id}`, `PATCH /products/{id}` (partial update), `PUT /products/{id}` (full replacement), `DELETE /products/{id}`.
- Validation at the edge (`422`) plus database constraints; `409` for a duplicate SKU.
- Liveness (`GET /health/`) and readiness (`GET /health/ready`) endpoints.
