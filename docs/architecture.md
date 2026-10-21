# Pocket architecture

Pocket is an expense-sharing service built with FastAPI, SQLAlchemy Core and SQLite. Its static web interface uses HTML, CSS and vanilla JavaScript with locally served assets. This document records the implemented design, including the assignment's equal-split expense flow, smart settlement suggestions and manual repayment recording.

## Scope and assumptions

The service creates users and groups, adds group members, records shared expenses, lists histories and calculates remaining balances. Smart settlement suggestions are the mandatory product enhancement. Repayment recording is the included settlement bonus. Participant selection and a web interface are additional features.

Pocket records events that happen outside the application. It does not move money, verify payments or authenticate the selected recorder. Currency is INR only. Duplicate names are permitted and integer IDs identify records. Groups may be empty or contain one member.

Financial records are creation-only. Editing, deletion, reversal, membership removal, custom unequal splits, currencies, categories, payment gateways and cross-group balances are outside the implemented scope.

## Application layers

| Module | Responsibility |
| --- | --- |
| app/main.py | Application factory, error responses, OpenAPI and static page |
| app/routes.py | HTTP inputs, response models and replay response status |
| app/schemas.py | Strict validation and documented response shapes |
| app/services.py | Transactions, existence and membership checks, financial writes and histories |
| app/accounting.py | Pure integer splitting, summaries and suggestions |
| app/database.py | Configured connections and explicit transaction boundaries |
| app/models.py | SQLAlchemy table metadata, checks, relationships and indexes |
| app/seed.py | Explicit, atomic demo initialization |
| migrations/ | Reproducible Alembic schema migration |
| app/static/ | One responsive interface and exact money conversion |

Routes delegate business operations to synchronous services. Services acquire independent connections and own complete transactions. Accounting functions have no HTTP or persistence dependencies. Balances and suggestions are derived rather than stored.

## Money and equal splitting

Storage and API requests use integer paise. Rs 1,200.00 is amount_paise 120000. Positive stored amounts are limited to SQLite's signed 64-bit maximum, 9223372036854775807. Validation rejects floats, numeric strings, booleans, zero, negative amounts and values outside that range. Derived totals are summed in Python so they can exceed a single stored amount's limit.

The interface accepts decimal rupee strings with at most two fractional digits. BigInt conversion and exact JSON token handling avoid binary floating-point rounding and unsafe JavaScript number conversion.

For an amount A and N distinct participants, sort user IDs ascending. Assign A // N to each participant and one additional paisa to the first A % N IDs. The saved shares sum exactly to the expense amount. Zero-valued shares remain valid, including a one-paisa expense shared by three members. Fixed ID ordering is deterministic but slightly favors lower IDs in remainder allocation.

Omitting participant_ids selects all current group members at expense creation. An explicit list selects a subset and may exclude the payer. Empty, null, repeated and nonmember selections are invalid. Shares are snapshots and later membership additions never change them.

The payer receives spending credit. recorded_by identifies who entered the record and grants no financial credit by itself. Both must belong to the group.

## Accounting model

For each member:

```text
net_balance_paise = paid_paise - share_paise
                  + repayments_sent_paise - repayments_received_paise
```

Positive means the member should receive money. Negative means the member still owes money. Zero means currently settled. Repayments change remaining balances but not expense totals or historical shares.

Every group summary includes all members in ID order, including members without activity. The sum of member net balances is zero. Total outstanding equals the sum of positive net balances and the absolute sum of negative balances. Group totals, member figures and suggested payment routes come from one consistent read snapshot.

Remaining group net positions determine current obligations. If Rahul owes Mohit Rs 100 and Mohit owes Ankit Rs 100, Rahul can pay Ankit Rs 100 to settle the group. Original expense records remain available, but their original pairs are not presented as still outstanding after an indirect settlement.

## Mandatory enhancement: smart settlement suggestions

A net balance tells someone how much they owe, but not whom to pay. Concrete payment routes help a group finish its accounts without manually matching creditors and debtors.

The algorithm separates negative members into debtors and positive members into creditors. It sorts each list by initial outstanding magnitude descending, then user ID ascending. Two pointers transfer the smaller remaining debt or credit and advance whichever side reaches zero. The fixed lists are not re-sorted after transfers.

This deterministic algorithm uses exact integer arithmetic, costs O(n log n) for sorting and O(n) for matching, and produces a valid clearing plan. It is not guaranteed to minimize the number of transfers globally. Simplicity and reproducible output take priority over combinatorial optimization.

The core balances endpoint includes suggested_payments. The focused settlement-suggestions endpoint uses the same calculation. Suggestions are never stored and never create repayments automatically.

## Bonus: repayment recording

A recorded repayment contains the group, sender, recipient, recorder, amount and timestamp. Any current member may enter it. The sender must have negative net balance and the recipient positive net balance. The amount cannot exceed either the remaining debt or credit. Self-payments and parties outside the group are rejected.

Full and partial repayments are supported. A debtor can repay any current creditor within the limits, independently of a particular expense or displayed suggestion. Suggested payment rows only prefill an editor; explicit Save records the repayment.

## Schema and constraints

Six tables form the source of truth:

| Table | Key data and integrity |
| --- | --- |
| users | Integer id; trimmed nonblank name up to 100 characters, not unique |
| groups | Integer id; same name rules |
| group_members | Non-null composite primary key (group_id, user_id), foreign keys and UTC joined_at |
| expenses | Integer id, group, payer, recorder, positive integer amount, trimmed nonblank description up to 500 characters, UTC timestamp and optional retry metadata |
| expense_shares | Non-null composite primary key (expense_id, user_id), foreign keys and nonnegative integer share |
| settlements | Integer id, group, sender, recipient, recorder, positive integer amount, UTC timestamp and optional retry metadata; sender differs from recipient |

Payer, recorder, sender and recipient use composite foreign keys to group_members. Money checks use SQLite typeof to enforce integer storage. All columns are non-null except request_id and request_fingerprint, which must be present or absent together. Foreign keys are enabled on every application, migration, seed and test connection. Default restrictive deletion protects financial history.

Request IDs are unique within their financial table; multiple null values are allowed. Expense and settlement history indexes use (group_id, created_at, id). Shares have a user_id index. Timestamps are server-generated sortable UTC text.

Participant membership, share sums and repayment caps are cross-row invariants enforced by services inside atomic transactions. Direct SQL can bypass those cross-row rules. Avoiding sum-maintaining triggers keeps the assignment implementation small and understandable.

## Transactions and concurrency

SQLite driver implicit transaction starts are disabled. SQLAlchemy begin events explicitly issue BEGIN for reads and BEGIN IMMEDIATE for writes. Financial writes acquire the write reservation before replay lookup, membership reads or balance checks.

The expense and all its share rows commit together. Any failure rolls back the complete operation. Overlapping repayments serialize, allowing the next transaction to check the already-updated remaining balances. A bounded busy wait defaults to 5000ms, configurable with POCKET_BUSY_MS. Exhausting it returns retryable HTTP 503.

Multi-query balance summaries and history counts/pages share a read transaction without taking a write reservation. There are no caches, background workers or mutable balance tables. SQLite's serialized writes are a deliberate single-instance tradeoff.

## Retry protection

Financial requests accept an optional UUID request_id. The UI always supplies one, disables submission while pending, preserves an ID for an unchanged retry and creates a new one for an edited or new submission. UI retry state lasts only for the current page session.

A SHA-256 fingerprint covers validated input plus group context, excluding the request ID. Descriptions are trimmed and explicit participant IDs sorted. Omitted participants retain an omitted-default marker; retries do not expand them against today's membership.

A matching saved ID and fingerprint returns the original resource with HTTP 200 before checking current membership or balances. A changed fingerprint returns HTTP 409. A new record returns HTTP 201. Retry metadata is committed with the record and fingerprints do not appear in responses.

Request IDs are unique across groups within each financial table, with separate expense and repayment namespaces. Requests without an ID have no duplicate-retry protection.

## API and validation

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST / GET | /users | Create / list users |
| POST / GET | /groups | Create / list groups |
| POST / GET | /groups/{group_id}/members | Add existing user / list members |
| POST / GET | /groups/{group_id}/expenses | Record expense and shares / history |
| POST / GET | /groups/{group_id}/settlements | Record repayment / history |
| GET | /groups/{group_id}/balances | Totals, members and suggested payment routes |
| GET | /groups/{group_id}/settlement-suggestions | Focused clearing suggestions |

Group context belongs in the URL. Financial requests require recorded_by in addition to the actual payer or payment parties. This intentionally differs from the assignment's literal rupee-valued expense payload: explicit paise fields avoid ambiguous units, group-scoped paths keep boundaries clear, and a recorder field distinguishes entering a record from paying.

Validation order is syntax, financial replay lookup, group existence, referenced users, membership and business limits. Missing records return 404; invalid shapes, money, participants, UUIDs, self-payments and existing nonmembers return 422. Duplicate membership, conflicting request IDs and incompatible or excessive repayments return 409. Exhausted write contention returns 503. Unexpected failures return 500 without SQL or stack traces in responses.

All errors use an error object with code, message and details. The OpenAPI schema and interactive docs are generated from typed request and response models.

Histories accept limit 1 to 100, default 50, and nonnegative offset, default zero. Ordering is created_at descending, then id descending. Responses contain items, total, limit and offset. Expense history includes saved shares; both histories include the recorder. Offset pagination is simple but new entries can shift later pages.

## Assignment example

Create Mohit, Rahul and Ankit, create Goa Trip and add all three members. Record Dinner for amount_paise 120000, paid_by Mohit and recorded_by Mohit, omitting participant_ids to exercise the all-member default.

Three saved shares are 40000 each, including Mohit's. The balance endpoint suggests Rahul to Mohit 40000 and Ankit to Mohit 40000. Recording Rahul's repayment of 40000 leaves Mohit +40000, Rahul zero and Ankit -40000. Dinner spending stays 120000.

The explicit seed uses a larger regression example: Dinner Rs 1,200 paid by Mohit for everyone, Taxi Rs 600 paid by Rahul for Rahul and Ankit, and Snacks Rs 300 paid by Ankit for Mohit. Each member's share totals Rs 700; initial nets are Mohit +Rs 500, Rahul -Rs 100 and Ankit -Rs 400. Rahul repaying Rs 60 leaves +Rs 440, -Rs 40 and -Rs 400 respectively.

See the [README walkthrough](../README.md#copyable-pdf-dinner-walkthrough) for runnable curl requests.

## Interface and delivery

The UI follows one continuous group page: a sticky back/switcher header, spending hero, People, Add an expense, Who pays whom and Activity. The UI displays rupees, labeled financial status and human-readable errors. All members start selected for an expense; payer and recorder can differ. Activity shows the latest 50 records, with a switch between expense and repayment histories. The API retains pagination.

All interface assets, including the licensed font, are served locally. There is no frontend framework, build step or external runtime dependency. Visual details are documented in [UI design](ui-design.md).

Alembic initializes a fresh database before the app runs. The app does not automatically migrate or seed on startup. The Docker command explicitly migrates before starting one Uvicorn worker. POCKET_DATA_DIR chooses storage, defaulting to data. Docker mounts its persistent named volume at /data. Explicit seeding refuses nonempty data and is atomic.

Tests use isolated temporary databases initialized by the migration. They cover accounting invariants, strict validation, transaction rollback, replay, concurrency, lock contention, histories and seed refusal. Actual submission verification and unavailable checks are recorded in the [README](../README.md#verification).

## Tradeoffs and future work

The main tradeoffs are deterministic but nonoptimal payment matching, fixed-ID remainder bias, serialized SQLite writes, explicit service validation instead of sum triggers and offset pagination that may shift.

With more time, improvements would include authenticated identities, a carefully designed correction/reversal workflow, stronger repayment verification and a database/deployment model suited to multiple instances. These are future extensions rather than claims about the current service.
