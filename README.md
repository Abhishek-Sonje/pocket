# Pocket

Pocket is an expense-sharing service for the Decentro SDE Intern assignment. Create a group, record shared expenses, see who should pay whom, and record full or partial repayments.

**Pocket records payments that happen outside the app.** It does not send money, verify payments or authenticate identities.

## Setup and running

Use Python 3.14. The local checks were run with Python 3.14.0 on Windows. Direct dependencies are pinned in requirements.txt; requirements-dev.txt includes those dependencies plus pytest, HTTPX and Ruff. Node is needed only for the JavaScript checks. There is no frontend build step.

From the repository root on Windows:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
```

For runtime-only installation, use requirements.txt instead. Open [Pocket](http://localhost:8000), [API docs](http://localhost:8000/docs), [ReDoc](http://localhost:8000/redoc) or [OpenAPI JSON](http://localhost:8000/openapi.json).

The database defaults to data/pocket.db and is created by the migration. Application startup does not migrate, create tables or seed automatically. Run commands from the repository root.

### Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| POCKET_DATA_DIR | data | Directory containing pocket.db |
| POCKET_BUSY_MS | 5000 | SQLite lock wait in milliseconds |

The app reads process environment variables. It does **not** load .env files automatically. [.env.example](.env.example) documents optional nonsecret values; set them in your shell before migration, seeding and startup.

```powershell
$env:POCKET_DATA_DIR = "data"
$env:POCKET_BUSY_MS = "5000"
```

On macOS/Linux, use export POCKET_DATA_DIR=data and export POCKET_BUSY_MS=5000. Migrations and the app must use the same storage directory.

### Explicit demo seed

After migration, before entering other data:

```powershell
.venv/Scripts/python.exe -m app.seed
```

Use .venv/bin/python on macOS/Linux. The seed creates Goa Trip, Mohit, Rahul and Ankit, plus Dinner Rs 1,200 for everyone paid by Mohit, Taxi Rs 600 for Rahul and Ankit paid by Rahul, and Snacks Rs 300 for Mohit paid by Ankit. Total spending is Rs 2,100. Initial remaining balances are Mohit +Rs 500, Rahul -Rs 100 and Ankit -Rs 400.

Seeding is atomic and refuses any database containing users or groups. Running it twice returns a nonzero exit on the second run without duplicating records. Restarting the app never seeds automatically.

## UI flow

Create a group on the home page. An open group has a sticky back/group-switcher header, a spending total and a labeled remaining-status pill.

1. Add people by name in one click, or select an existing user. Duplicate names receive IDs only when needed.
2. Add an expense with a rupee amount and payer. All members start selected; uncheck participants if appropriate. Everyone selects all again. At least one participant is required. Advanced contains Entered by, defaulting to the payer.
3. Review suggested payments and member spending/share/status. Mark as paid opens an editable amount with Save and Cancel; opening it records nothing. Save records a payment already completed outside Pocket. Partial repayments and a separate From/To/Amount form are supported.
4. Switch Activity between expenses and repayments. Each view shows the newest 50 entries with recorder details.

Pending writes disable submit controls. An unchanged retry retains its request ID after failure; edited or new submissions receive a new ID. Retry state lasts for the open page, not across reloads. Successful writes refresh totals, suggestions, balances and activity. The static interface and licensed font are served locally, with no CDN or external runtime assets. See [UI design](docs/ui-design.md).

## Docker and persistence

Docker uses Python 3.14-slim and installs the same pinned runtime requirements. Test and lint packages are excluded from the runtime image.

```sh
docker compose up --build -d
docker compose exec pocket python -m app.seed
docker compose down
docker compose up -d
```

The seed command is optional and requires an empty migrated database. The container command applies Alembic migrations before starting one Uvicorn worker on port 8000.

Compose mounts the named pocket-data volume at /data. Its actual name is prefixed by the Compose project name. Stopping or recreating the container retains data. docker compose down -v deletes the volume and its records. No database or local virtual environment is included in the source submission or image build context.

## Architecture and schema

FastAPI handles HTTP, Pydantic validates inputs, SQLAlchemy Core manages records and SQLite provides persistence. Services own transactions; accounting is pure integer logic. No mutable balance table, background worker, cache or separate frontend service is needed.

| Module | Responsibility |
| --- | --- |
| app/main.py | Application factory, errors, static page and generated API documentation |
| app/routes.py, app/schemas.py | Endpoint contracts, strict inputs and typed outputs |
| app/services.py | Existence/membership checks, transactions, retry lookup and histories |
| app/accounting.py | Equal splits, net summaries and deterministic payment suggestions |
| app/database.py | Connections, foreign keys and explicit transaction boundaries |
| app/models.py | Six tables, relationships, checks and indexes |
| migrations/versions/001_initial.py | Fixed initial schema, independent of current application models |
| app/seed.py | Explicit atomic demo seed |
| app/static/ | HTML, CSS, JavaScript and local licensed font |

| Table | Important columns and constraints |
| --- | --- |
| users | Integer id; trimmed nonblank name up to 100 characters; duplicate names allowed |
| groups | Integer id; same name rules |
| group_members | Non-null composite PK (group_id, user_id), group/user FKs and UTC joined_at |
| expenses | Integer id; group, payer, recorder, positive integer amount_paise, trimmed description up to 500 characters, UTC timestamp, optional retry metadata |
| expense_shares | Non-null composite PK (expense_id, user_id), expense/user FKs and nonnegative integer share_paise |
| settlements | Integer id; group, sender, recipient, recorder, positive integer amount, UTC timestamp and optional retry metadata; sender differs from recipient |

Payer, recorder, sender and recipient use composite membership foreign keys. Foreign keys are enabled on every application, migration, seed and test connection. SQLite typeof checks enforce integer money storage. All columns are non-null except the retry ID/fingerprint pair, which must be present or absent together. Unique request IDs allow multiple nulls. Default restrictive deletion protects financial history.

History indexes use (group_id, created_at, id) on expenses and settlements; shares have a user_id index. Participant membership, share sums and repayment caps are cross-row rules enforced by services inside atomic writes. Raw SQL can bypass these cross-row rules; row checks and foreign keys still apply.

See [architecture and decisions](docs/architecture.md) for the full design.

## Money, balances and assumptions

INR only. API and storage use **integer paise**, not floating-point rupees: amount_paise 120000 means Rs 1,200.00. The UI accepts rupees with up to two decimals and formats exactly two decimals using BigInt/string conversion. Its exact JSON handling preserves integers beyond JavaScript's safe-number limit.

Stored positive amounts are limited to 9223372036854775807. Numeric strings, floats, booleans, zero, negatives and larger stored amounts are rejected. Derived group totals use Python integers and may exceed the per-record storage limit.

Equal splits sort participant IDs, assign amount // count to each, then one extra paisa to the first amount % count IDs. Rs 100.00 shared by three becomes Rs 33.34, Rs 33.33 and Rs 33.33. A one-paisa expense shared by three preserves shares 1, 0 and 0. This deterministic rule has a small fixed-ID remainder bias.

Omitting participant_ids selects all current members at creation. Explicit subsets can exclude the payer. Empty, null, duplicate and nonmember selections fail. Saved shares never change when members are added. paid_by gets spending credit; recorded_by only records who entered the event.

```text
net_balance_paise = paid_paise - share_paise
                  + repayments_sent_paise - repayments_received_paise
```

Positive means gets back, negative means owes and zero means settled. Every member appears in the summary. Net balances sum to zero; total outstanding is the sum of positive balances. Repayments never alter trip spending or historical shares. Current obligations use group net positions, so valid indirect repayments can clear obligations without following original expense pairs.

Names may repeat. Empty and one-member groups are supported. Identity and payments are unverified. Financial history is creation-only; there is no editing, deletion, reversal or member removal. Unequal custom amounts, currency conversion, categories and authentication are outside scope.

## Mandatory enhancement and bonus

**Smart settlement suggestions are the mandatory enhancement.** A remaining balance alone leaves members asking whom to pay. Concrete sender/recipient/amount routes make it possible to close a group's accounts without manual matching.

The algorithm sorts debtors and creditors by initial outstanding magnitude descending, then user ID ascending. Two pointers match the smaller remaining debt or credit and advance when a side reaches zero. It does not re-sort after transfers. The calculation is deterministic, exact, O(n log n), and shared by the balances and settlement-suggestions endpoints.

This trades globally minimal transfer count for a small, reproducible algorithm. It produces a valid clearing plan but does not guarantee the fewest possible transfers. Suggestions are calculated, never stored or recorded automatically.

**Repayment recording is the included bonus.** Full and partial repayments reduce remaining debt while preserving original expense history. Any member can record a payment, but sender and recipient must be a current debtor and creditor, and the amount cannot exceed either remaining position. Participant selection, personal summaries and the UI are additional features.

## Transactions and retry protection

Each service operation uses an independent connection. SQLite driver implicit BEGIN is disabled; SQLAlchemy explicitly issues BEGIN for reads and BEGIN IMMEDIATE for writes. Writes reserve the database before replay lookup and balance validation. Expense/share writes roll back together, and overlapping repayments serialize before their limits are checked.

Multi-query summaries and history counts/pages share a read snapshot. Totals are summed in Python to avoid SQLite aggregate overflow. Exhausting the configured lock wait returns retryable HTTP 503.

Financial requests optionally accept a UUID request_id. Matching ID/input returns the original record with 200; a new creation returns 201; changed input with the same ID returns 409. IDs are unique across groups within each financial table, with separate expense and repayment namespaces.

An atomic SHA-256 fingerprint covers validated input and group context, trims descriptions and sorts explicit participants. Omitted participants retain an omitted-default marker. Replay is checked before current-state membership or balance validation, so an uncertain payment can be retried even after its original request cleared the debt. Fingerprints are not exposed.

Requests without IDs have **no duplicate-retry protection**. Reuse the same ID and input when retrying an uncertain financial request.

## API

All bodies are JSON. Unknown fields fail validation. Interactive request and response schemas are available at /docs.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST / GET | /users | Create / list users |
| POST / GET | /groups | Create / list groups |
| POST / GET | /groups/{id}/members | Add existing user / list members |
| POST / GET | /groups/{id}/expenses | Record expense/shares / history |
| POST / GET | /groups/{id}/settlements | Record repayment / history |
| GET | /groups/{id}/balances | Totals, members and explicit suggested payment routes |
| GET | /groups/{id}/settlement-suggestions | Focused clearing suggestions |

Missing records return 404. Invalid syntax, money, UUID, participants, membership or self-payment return 422. Duplicate membership, reused ID with changed input, and incompatible/excessive repayment return 409. Lock timeout returns 503. Unexpected failures return 500 without exposing SQL or stack traces.

Error envelope:

```json
{"error":{"code":"repayment_exceeds_balance","message":"This repayment exceeds the remaining debt or credit.","details":[]}}
```

Validation order is syntax, replay lookup, group existence, user existence, membership and balance limits. Existing nonmembers return 422; nonexistent users return 404.

Histories accept limit from 1 to 100, default 50, and nonnegative offset, default zero. They sort by UTC created_at descending, then id descending, and return items, total, limit and offset. Expenses include saved shares; both histories include recorded_by. New entries can shift offset-based pages.

### Copyable PDF dinner walkthrough

Run the server against a migrated database. This Bash example uses curl and Python 3 to retain returned IDs, so it does not assume an empty ID sequence. On systems where the executable is python3, change the json_id helper accordingly. The example creates its own new users and Goa Trip group; it does not require seeding.

```bash
set -euo pipefail
BASE=http://127.0.0.1:8000
json_id() { python -c 'import json,sys; print(json.load(sys.stdin)["id"])'; }
post() {
  curl --fail-with-body --silent --show-error     -H 'Content-Type: application/json' --data "$2" "$BASE$1"
}

MOHIT=$(post /users '{"name":"Mohit"}' | json_id)
RAHUL=$(post /users '{"name":"Rahul"}' | json_id)
ANKIT=$(post /users '{"name":"Ankit"}' | json_id)
GROUP=$(post /groups '{"name":"Goa Trip"}' | json_id)

for USER in "$MOHIT" "$RAHUL" "$ANKIT"; do
  post "/groups/$GROUP/members" "{\"user_id\":$USER}"
  echo
done

# Omit participant_ids to use all current members.
post "/groups/$GROUP/expenses"   "{\"description\":\"Dinner\",\"amount_paise\":120000,\"paid_by\":$MOHIT,\"recorded_by\":$MOHIT}"
echo

curl --fail-with-body --silent --show-error "$BASE/groups/$GROUP/balances"
echo
# Three saved shares of 40000.
# Suggestions: Rahul to Mohit 40000, Ankit to Mohit 40000.

post "/groups/$GROUP/settlements"   "{\"from_user\":$RAHUL,\"to_user\":$MOHIT,\"recorded_by\":$RAHUL,\"amount_paise\":40000}"
echo
curl --fail-with-body --silent --show-error "$BASE/groups/$GROUP/balances"
echo
# Mohit +40000, Rahul 0, Ankit -40000.
# Only Ankit to Mohit 40000 remains; total expenses stay 120000.
```

The assignment's rupee amount 1200 becomes amount_paise 120000. The group belongs in the URL, and recorded_by is an additional required field. These intentional variations provide unambiguous units, group boundaries and a distinction between payer and recorder. The literal PDF request body is not accepted unchanged.

For retry-protected submissions, add a UUID request_id to an expense or repayment body and retain it for an unchanged retry.

## Tests and code quality

Windows commands:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
node tests/money.test.cjs
node --check app/static/app.js
node --check app/static/money.js
```

Use .venv/bin/python on macOS/Linux. To format Python, run python -m ruff format . with the virtual environment active. Ruff configuration is in pyproject.toml.

Tests use fresh temporary databases initialized through Alembic. They cover the dinner and larger trip examples, 500 generated accounting cases, shares, strict validation, full/partial repayment, retry replay/conflicts, rollback, foreign keys, raw constraints, read snapshots, separate-connection concurrency, real lock contention, histories, group isolation and seed refusal.

## Verification

Actual submission checks on 22 October 2026:

| Check | Result |
| --- | --- |
| Full pytest suite, Windows Python 3.14.0 | 40 passed; one third-party Starlette/AnyIO deprecation warning |
| Ruff 0.14.1 check and format --check | Passed; all 18 Python files formatted |
| Node exact-money and both JavaScript syntax checks | Passed |
| Fresh Alembic migration | Passed; revision 001 and six application tables |
| Explicit seed run twice | First succeeded; second refused with a nonzero exit, with all table counts unchanged |
| Real localhost Uvicorn dinner scenario | Passed: three Rs 400 shares; Rahul and Ankit routes; Rahul repayment leaves only Ankit |
| Real HTTP partial repayment and retry | Passed: Ankit Rs 150 repayment leaves Rs 250; replay creates no duplicate |
| Concurrent identical real HTTP expense requests | HTTP 201 and 200, one expense record |
| Docker image build and local run, Python 3.14.8 | Passed; runtime pip check passed |
| README curl walkthrough against Docker | Passed with only the host port changed to 18000 |
| Docker container recreation using the same named volume | Passed; saved balances and records preserved |
| Docker Compose configuration | Valid |
| Git diff whitespace check | Passed |

Python logic ASTs, excluding module import organization, and all static asset bytes were compared before and after cleanup: unchanged. Tests received formatting and import organization only; assertions and intent were retained.

Browser rendering, keyboard interaction and responsive checks were not run because no connected browser was available. HTTP/static-asset checks do not substitute for those checks. Verification servers, test databases, container and test volume were cleaned up; no database is shipped.

## Tradeoffs and future improvements

SQLite serializes writes and suits one application instance; a multi-instance service would need a more suitable database/deployment model. Service checks keep cross-row validation explicit instead of introducing sum triggers. Deterministic remainders have fixed-ID bias. Greedy matching does not guarantee minimal transfers. Offset pagination can shift when new records arrive.

With more time: authenticated identity, a carefully designed correction/reversal workflow, stronger repayment verification and scaling beyond a single SQLite instance. These are future extensions, not claims about current capabilities.
