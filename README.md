# Pocket

Pocket is a small expense-sharing app built for the Decentro SDE Intern assignment. Create a group, record shared expenses, see who should pay whom, and record full or partial repayments.

**Pocket only records payments made outside the app.** It does not send money or verify payments or identities. There is no login. Use local/demo data.

## Run locally

Tested with Python **3.14.0** on Windows. Dependencies are pinned in `requirements.txt`. Node is only needed for the standalone JavaScript checks; the app has no frontend build step.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

On macOS/Linux use `.venv/bin/python` in place of `.venv/Scripts/python.exe`.

Open [Pocket](http://localhost:8000), [interactive API docs](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc), or [OpenAPI JSON](http://localhost:8000/openapi.json).

The database defaults to `data/pocket.db`. Set `POCKET_DATA_DIR` to choose a persistent directory. Migrate and start with the same environment. Startup never creates tables or seeds records automatically.

Optional demo seed, **after migration and before entering other data**:

```powershell
.venv/Scripts/python.exe -m app.seed
```

This creates Goa Trip with Mohit, Rahul and Ankit and the dinner/taxi/snacks example below. It refuses a nonempty database, rolls back on failure and never duplicates data. Restarting the server preserves records.

## Docker

```sh
docker compose up --build -d
# Optional: seed the fresh database once
docker compose exec pocket python -m app.seed
docker compose down
docker compose up -d
```

The named `pocket-data` volume is mounted at `/data`. Compose prefixes the volume name with its project name. Restarting or recreating the container preserves records; `docker compose down -v` deletes the volume and its records. The container applies migrations before starting one Uvicorn worker. No automatic demo seed runs.

## Using the page

1. Create a group. Expand **Manage people**, create users, and add them to the group. Existing users can join multiple groups. Labels include IDs because duplicate names are allowed.
2. Choose **Adding as**. This records who entered an expense or repayment, not verified identity.
3. Enter an expense in rupees. **Did you pay?** defaults to Yes. Choose No to select a different payer. All current members start selected as participants; uncheck people or use **Clear all**. Select at least one before saving. The payer may be excluded.
4. Review paid-upfront amounts, personal shares, remaining balances and suggested payments. **Use amount** fills the repayment form; it does not record a payment.
5. Once someone has paid outside Pocket, explicitly save the repayment. Partial repayments are supported. Histories include the recorder and saved expense shares, with Previous/Next controls.

Controls prevent repeated submission while a write is pending. An unchanged retry retains its request ID after a failure; editing the form, changing the recorder or starting a new submission assigns a new ID. This retry state lasts for the open page, not across reloads. Successful writes refresh balances, suggestions and both histories. Names and descriptions are rendered as text.

## Accounting and money

INR only. API and storage use **integer paise**, never floating-point rupees. `120000` paise is ₹1,200.00. Stored positive amounts are at most `9223372036854775807`; derived group totals use Python integers and may exceed that per-record limit. API amounts reject strings, floats, booleans, zero, negative numbers and values outside the stored range.

The page converts decimal strings using `BigInt`, rejects more than two fractional digits and emits exact JSON integer tokens. Incoming integer JSON tokens are preserved as strings before parsing, then formatted with `BigInt`; even amounts beyond JavaScript's safe-number range retain every paisa. IDs are likewise preserved. No binary-float multiplication or silent rounding is used.

For equal splitting, sort participant IDs, assign `amount // count` to each, then one extra paisa to the first `amount % count` IDs. ₹100.00 / 3 becomes ₹33.34, ₹33.33, ₹33.33. One paisa / 3 creates all three share rows: 1, 0, 0. The fixed tie-break slightly biases remainder assignment toward lower IDs; rotation is deliberately excluded.

Omitting `participant_ids` splits among all members **at creation time**. An explicit list selects beneficiaries and can exclude the payer. Empty, duplicate or null lists fail. Historical shares are saved and never recomputed when membership changes. `paid_by` receives credit; `recorded_by` receives none merely for entering a record.

For every member:

```text
net_balance_paise = paid_paise - share_paise
                  + repayments_sent_paise - repayments_received_paise
```

Positive means should receive; negative means owes; zero means currently settled. Every member appears, including members with no activity. The sum of net balances is zero. Personal shares and upfront payments each sum to total group expenses. Outstanding is the sum of positive net balances. Repayments change remaining balances but never trip spending or historical shares.

Current obligations are group net positions. If Rahul owes Mohit ₹100 and Mohit owes Ankit ₹100, Rahul can repay Ankit ₹100 and clear everyone. Original records remain in history; original expense pairs are not displayed as still payable afterward. Groups never cancel each other's debts.

## Product enhancement

**Smart settlement suggestions are the mandatory product enhancement.** At the end of a trip, members need concrete payment routes, not just totals. Both `/balances` and `/settlement-suggestions` show sender, recipient and amount from the same accounting function.

The algorithm initially sorts debtors and creditors by outstanding magnitude descending, then user ID ascending. Two pointers match the smaller remaining debt/credit; lists are not re-sorted after transfers. It is deterministic, uses exact integers, runs in O(n log n), and clears all net balances. It is **not guaranteed to minimize transfer count globally**. Suggestions are calculated, never stored or automatically recorded.

**Repayment recording is the included optional settlement bonus.** Any member may record a transfer between a current debtor and creditor. The amount cannot exceed either remaining debt or credit. Self-payments, nonmembers and invalid amounts fail. No confirmation or bank verification is implied. Participant selection, personal summaries and the web interface are additional improvements.

The seeded regression trip is:

| Expense | Amount | Payer | Participants |
|---|---:|---|---|
| Dinner | ₹1,200 | Mohit | All three |
| Taxi | ₹600 | Rahul | Rahul, Ankit |
| Snacks | ₹300 | Ankit | Mohit |

Everyone's personal share is ₹700. Nets are Mohit +₹500, Rahul −₹100, Ankit −₹400. After Rahul repays Mohit ₹60, suggestions are Ankit → Mohit ₹400, then Rahul → Mohit ₹40. Trip expenses stay ₹2,100.

## Architecture and schema

Ordinary synchronous FastAPI + SQLAlchemy Core + SQLite; no separate frontend, workers, cache or mutable balances.

| File | Responsibility |
|---|---|
| `app/main.py` | App creation, error handlers, static page |
| `app/routes.py` | HTTP inputs, response models, replay status |
| `app/schemas.py` | Strict inputs and documented outputs |
| `app/services.py` | Transactions, membership/existence checks, retry lookup, history, financial writes |
| `app/accounting.py` | Pure integer splits, summaries and suggestions |
| `app/database.py` | Connections, foreign keys, explicit transaction boundaries |
| `app/models.py` | Six table definitions and indexes |
| `migrations/versions/001_initial.py` | Fixed initial schema, independent of application models |
| `app/seed.py` | Explicit, atomic demo initialization |
| `app/static/` | Single page, CSS and minimal JavaScript |

| Table | Columns and integrity |
|---|---|
| `users` | Integer PK `id`, trimmed nonblank `name` ≤100; names need not be unique |
| `groups` | Integer PK `id`, same name rules |
| `group_members` | Non-null composite PK `(group_id,user_id)`, FKs to groups/users, server UTC `joined_at` |
| `expenses` | Integer PK, group FK, payer, recorder, positive integer `amount_paise`, trimmed description ≤500, server UTC `created_at`, optional unique `request_id` and fingerprint |
| `expense_shares` | Non-null composite PK `(expense_id,user_id)`, expense/user FKs, nonnegative integer `share_paise` |
| `settlements` | Integer PK, group FK, sender, recipient, recorder, positive integer amount, UTC timestamp, optional unique request ID and fingerprint; sender differs from recipient |

Payer/recorder/sender/recipient use composite membership FKs `(group_id,user_id)`. All columns are non-null except retry metadata, which must be present or absent together. SQLite `typeof` checks enforce integer money storage. Foreign keys are enabled on every application, migration, seed and test connection. Default restrictive deletion preserves financial history. Timestamps use sortable UTC ISO text.

History indexes are `(group_id,created_at,id)` on expenses and settlements. Shares have a `user_id` index. Primary keys enforce membership/share uniqueness; unique request IDs allow multiple NULLs. No redundant balance or suggestion tables exist.

Participant membership, share sums and repayment balance caps are **service-only cross-row invariants** checked inside atomic writes. Raw SQL can violate these invariants even though row checks/FKs remain enforced. This keeps the small assignment understandable instead of adding sum-maintaining triggers.

## Transactions and retries

Services own one transaction per operation. Each call uses an independent connection. SQLite driver implicit BEGIN is disabled, and the SQLAlchemy begin event explicitly emits `BEGIN` for reads or `BEGIN IMMEDIATE` for writes. Financial writes acquire the write reservation before replay lookup, membership reads or balance checks. A failure rolls back the expense and every share together. Concurrent overlapping repayments serialize; a second request sees the first payment's result before checking its cap.

Multi-query balances and history counts/pages share a read transaction and snapshot, without a write reservation. Totals are summed in Python to avoid SQLite aggregate overflow. SQLite serializes writes; this single-instance tradeoff is suitable for the assignment. A bounded wait defaults to 5 seconds (`POCKET_BUSY_MS` overrides it); exhausted locks return retryable 503.

Optional `request_id` is a UUID, unique across groups within each financial table; expense/repayment namespaces are separate. A SHA-256 fingerprint covers validated input and group context, trims descriptions and sorts explicit participants. Omitted participants remain an omitted-default marker instead of being expanded during retry comparison. Matching replay returns the original saved resource with 200 **before** checking today's membership/balances. Changed input returns 409. Metadata is saved atomically and fingerprints never appear in responses/OpenAPI.

Without an ID, every accepted request creates a new record: **there is no duplicate-retry protection**. Retry uncertain financial requests with the same ID and input.

## API

All bodies are JSON. Unknown body fields fail validation. User and group lists are simple arrays; member lists are ordered by ID. Responses use the documented integer fields. See `/docs` for full response schemas.

| Method | Path | Purpose |
|---|---|---|
| POST / GET | `/users` | Create / list users |
| POST / GET | `/groups` | Create / list groups |
| POST / GET | `/groups/{id}/members` | Add existing user / list members |
| POST / GET | `/groups/{id}/expenses` | Save expense and shares / history |
| POST / GET | `/groups/{id}/settlements` | Record repayment / history |
| GET | `/groups/{id}/balances` | Totals, every member summary and suggested payment routes |
| GET | `/groups/{id}/settlement-suggestions` | Focused `{group_id,suggestions}` response |

Creation returns 201; matching financial replay returns 200. Missing group/user → 404. Invalid syntax, money, UUID, membership, self-payment or participant selection → 422. Existing membership, conflicting request ID or incompatible/excessive repayment → 409. Exhausted SQLite lock wait → 503. Unexpected failures → 500 without SQL or stack traces in responses.

Validation order: syntax → replay lookup → group existence → all referenced users exist → membership → balance limits. Existing nonmembers yield 422; nonexistent users yield 404.

Consistent error envelope (framework validation adds field details):

```json
{"error":{"code":"repayment_exceeds_balance","message":"This repayment exceeds the remaining debt or credit.","details":[]}}
```

Financial histories accept `?limit=50&offset=0`, with limit 1–100 and offset ≥0. Newest UTC timestamp, then ID descending. Response: `{ "items": [...], "total": 12, "limit": 50, "offset": 0 }`. Expense items include sorted saved `shares`; both kinds include `recorded_by`. Offset pagination is intentionally simple: new records may shift later pages.

### Copyable assignment walkthrough

Run against a **fresh migrated database without the demo seed**. The following Python uses only the standard library and retains created IDs, so it does not assume sequence values. Save as a temporary script or paste into Python while the server runs:

```python
import json
from urllib.request import Request, urlopen

def api(path, body=None):
    request = Request("http://localhost:8000" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        return json.load(response)

mohit, rahul, ankit = [api("/users", {"name": name})["id"]
                       for name in ("Mohit", "Rahul", "Ankit")]
group = api("/groups", {"name": "Goa Trip"})["id"]
for user in (mohit, rahul, ankit):
    api(f"/groups/{group}/members", {"user_id": user})

# Omission exercises the required default: all current members.
expense = api(f"/groups/{group}/expenses", {
    "paid_by": mohit, "recorded_by": mohit,
    "amount_paise": 120000, "description": "Dinner"})
assert expense["shares"] == [{"user_id": user, "share_paise": 40000}
                             for user in sorted((mohit, rahul, ankit))]
balance = api(f"/groups/{group}/balances")
assert balance["suggested_payments"] == [
    {"from_user": user, "to_user": mohit, "amount_paise": 40000}
    for user in sorted((rahul, ankit))]
api(f"/groups/{group}/settlements", {
    "from_user": rahul, "to_user": mohit, "recorded_by": rahul,
    "amount_paise": 40000})
balance = api(f"/groups/{group}/balances")
assert {m["user_id"]: m["net_balance_paise"] for m in balance["members"]} == {
    mohit: 40000, rahul: 0, ankit: -40000}
print(json.dumps(balance, indent=2))
```

The original PDF's rupee `amount: 1200` becomes `amount_paise: 120000`. Group context is in the URL and `recorded_by` is an additional required field. These deliberate API variations prevent ambiguous money units, keep operations group-scoped and distinguish entry from payment. The literal PDF body is not accepted unchanged.

Example expense with selected participants and retry protection:

```json
{"paid_by":1,"recorded_by":2,"amount_paise":120000,"description":"Dinner","participant_ids":[1,2,3],"request_id":"11111111-1111-4111-8111-111111111111"}
```

Example saved expense:

```json
{"id":1,"group_id":1,"paid_by":1,"recorded_by":2,"amount_paise":120000,"description":"Dinner","created_at":"2026-10-21T12:00:00.000Z","shares":[{"user_id":1,"share_paise":40000},{"user_id":2,"share_paise":40000},{"user_id":3,"share_paise":40000}]}
```

## Verification

```powershell
.venv/Scripts/python.exe -m pytest -q
node tests/money.test.cjs
node --check app/static/app.js
```

Tests create fresh file-backed temporary databases through the actual Alembic migration. They never use the user's database. Coverage includes the assignment dinner/repayment scenario, the worked trip, 500 generated accounting cases, share snapshots, strict money, membership, retry replay/conflicts, full/partial repayment, rollback, foreign keys and raw constraints, separate-connection concurrency, actual write-lock timeout, pagination, group isolation and repeat-seed refusal.

Actual results on Python 3.14.0: **40 pytest tests passed**; exact-money Node checks and JavaScript syntax checks passed. One dependency deprecation warning concerns Starlette's AnyIO alias. Browser workflow/responsive execution is **pending: no browser connection is available**. Docker build/run/recreation is **pending: Docker Desktop's daemon is not running**. These are unverified checks, not claimed passes.

## Scope and tradeoffs

No authentication, verified payments, editing/deletion/reversal, member removal, custom unequal amounts, categories or currency conversion. Financial records are creation-only; new expenses can create new obligations after a group settles. One-member and empty groups are supported. Duplicate names are intentional.

Suggestions trade global transfer optimality for a small deterministic algorithm. SQLite trades write throughput for simple persistence. Service checks trade trigger complexity for explicit transactional validation. Remainder distribution has a fixed-ID bias; offset pages may shift.

With more time: authenticated identity, carefully designed corrections/reversals, repayment verification and a database suited to multiple instances. These are future scope, not unfinished required features.
