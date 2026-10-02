# N+1 queries: measured

**N+1** is the most common ORM performance bug: a list endpoint runs **1** query for the rows, then **1 more per row** to load a relationship. It passes every functional test, is fast on a small database, and slows down in proportion to page size in production.

## In this codebase

Each `Product` has many `Certification`s (`UL 10C`, `ANSI/BHMA A156.13 Grade 1`, ...). `GET /products` returns each product with its certifications.

SQLAlchemy relationships are **lazy** by default: `product.certifications` isn't loaded until something reads it. When `ProductRead` serializes a page of 20 products, it reads `certifications` on each one, and each read is a separate query.

## Measurement

20 products with 2 certifications each, `GET /products?limit=20`, with a fresh session, counting statements via SQLAlchemy's `before_cursor_execute` event:

| Loading strategy | SELECT statements | Shape |
|---|---|---|
| Lazy (default) | **21** | 1 for products, then `WHERE :id = certifications.product_id` × 20 |
| `selectinload(Product.certifications)` | **2** | 1 for products, 1 for all their certifications: `WHERE product_id IN (...)` |

Lazy loading grows with the page size (`1 + N`). Eager loading is constant: 2 queries whether the page has 5 products or 100. Each query is also a network round trip to Postgres, so at 1 ms per round trip, a 100-item page goes from ~2 ms to ~101 ms of pure latency before any query work.

## The fix

```python
select(Product).options(selectinload(Product.certifications)).order_by(Product.id).limit(...)
```

`get_product_or_404` also eager-loads, which turned out to matter for correctness as well as speed (see below).

**`selectinload` vs `joinedload`:** `joinedload` uses a single `LEFT JOIN`, but it repeats every product column once per certification and interacts badly with `LIMIT`, since it limits joined rows rather than products. `selectinload` issues a second query keyed by the products already loaded, which suits one-to-many collections and pagination. `joinedload` is the better fit for many-to-one (e.g. a certification's product).

## How it's guarded

`tests/test_query_counts.py` seeds 5 and then 20 products and asserts the list endpoint runs **exactly 2** SELECTs in both cases. Removing the `selectinload` fails the test (verified by deleting it).

**Test-fidelity trap:** tests share one session across requests, so products created during setup stay in the session's identity map *with their relationships already loaded*. A naive query-count test then passes even with lazy loading. The test empties the identity map first (`expunge_all()`), as a new production request would.

## Related bug found along the way: autoflush + lazy load

`PUT` set a new (duplicate) SKU on the product, then read `product.certifications`. That triggered a lazy load, and **autoflush** sent the pending `UPDATE` before the `SELECT`, so the unique violation was raised outside the `commit_or_409` handler and the client got a 500 instead of a 409. Eager-loading in `get_product_or_404` removed the surprise query, and with it the surprise flush.
