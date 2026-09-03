# High-risk request boundaries

## Scope and enforcement layers

This review covers public JSON request models and query parameters for Catalog,
Inventory, Product Content, and Execution. Response-only models are not treated
as request risks.

Every ordinary JSON request is subject to the global
`MAX_REQUEST_BODY_BYTES` transport limit. Field limits are additional business
and amplification boundaries; they do not replace the transport limit. A
request containing several individually valid large fields can therefore still
receive HTTP 413.

Schema violations return the standard HTTP 422 validation response. A cursor
that exceeds its encoded limit is rejected as an invalid cursor before Base64
decoding. Values beyond PostgreSQL `varchar` or `integer` capacity are rejected
before a transaction reaches persistence.

## Reviewed field families

| Field family | Business maximum | Technical maximum | Empty/null and normalization |
|---|---:|---:|---|
| Main content and HTML | 500,000 Unicode code points | global request-body byte limit | Required content rejects an empty string. Content is preserved; rendering and sanitization are separate concerns. |
| Descriptions and long explanatory text | 50,000 code points | global request-body byte limit | Optional fields accept `null` and retain the existing empty-string behavior. No Unicode normalization is applied to display text. |
| AI prompts | 100,000 code points | global request-body byte limit | Optional prompts accept `null`; empty and non-empty prompt text is preserved. |
| Notes, reasons, and link errors | 20,000 code points | global request-body byte limit | Optional fields accept `null` and retain the existing empty-string behavior; whitespace is not silently rewritten at the schema boundary. |
| Names, codes, slugs, references, URLs, and condition identifiers | Matching ORM `varchar(n)` size, generally 32–1,500 code points | matching PostgreSQL column size | Required identity fields use `min_length=1`; domain services retain their existing stable-code and trimming behavior. |
| User-defined regex patterns | 2,000 code points | global request-body byte limit plus runtime regex timeout | Empty create patterns are rejected. Length is not a substitute for a runtime timeout. |
| Bulk mutations and imports | 500 items | global request-body byte limit | Empty required batches are rejected; duplicate business keys retain their existing model validation. |
| Tags, aliases, examples, variables, and similar collections | 500 items, with bounded string members where applicable | bounded JSON structure and global body size | Optional collections retain existing null/default behavior. |
| Arbitrary JSON and `Any` values | 512 KiB encoded UTF-8 | depth 32, 20,000 nodes, 10,000 keys, 1,000 code points per key, 5,000 items per nested array | Only JSON-compatible, finite, acyclic values are accepted. |
| Search text | 500 Unicode code points | HTTP request-line limit remains an outer deployment boundary | Empty required searches are rejected; optional Catalog searches may be omitted. |
| Signed cursors | 4,096 ASCII characters | rejected before decoding | `null`/omitted selects the first page. Cursor signatures and filter binding remain unchanged. |
| Inventory quantities | 2,147,483,647 | PostgreSQL `integer` maximum | Existing non-negative and reservation/on-hand rules remain in force. |
| Attribute numeric thresholds | 24 digits with 8 decimal places for values; 5 digits with 4 decimal places for confidence | matching PostgreSQL `numeric` precision | Decimal input accepts JSON numbers or numeric strings and is validated before persistence. |

Pydantic string lengths count Unicode code points, not user-perceived grapheme
clusters and not UTF-8 bytes. For example, one emoji generally counts as one
character but four UTF-8 bytes; `e` followed by a combining acute accent counts
as two characters. The global transport limit therefore remains authoritative
for multi-byte or heavily escaped JSON.

## Structured JSON contract

The shared JSON validator performs an iterative walk before serialization. It:

- detects cycles without rejecting harmless repeated references;
- rejects non-string object keys and non-JSON Python values;
- rejects `NaN`, positive infinity, and negative infinity;
- bounds nesting, nodes, keys, key length, and nested array length;
- calculates the final compact UTF-8 representation with `allow_nan=False`;
- enforces the 512 KiB encoded limit.

The same contract is applied to:

- Execution job payloads;
- Catalog validation rules, defaults, examples, metadata, dependency rules,
  formula-preview values, and raw product-attribute values;
- Product Content source metadata, SEO structures, landing metadata, and prompt
  examples.

OpenAPI exposes the structural contract through deterministic `x-max-json-*`
extensions in addition to ordinary `maxLength` and `maxItems` constraints.

## High-amplification operations

The following operations have explicit item bounds in their request models:

- product attribute bulk write and validation;
- enterprise attribute bulk preview and commit;
- attribute group, definition, assignment, and legacy category reordering;
- attribute-template import;
- prompt/example and option-alias collections.

Rate limiting is a separate defense-in-depth layer. Batch validation remains
necessary even when a shared limiter is enabled because one accepted request
must have bounded database and CPU amplification.

## Query boundaries

All public signed cursor parameters expose a 4,096-character OpenAPI maximum
and `decode_cursor()` repeats that check as defense in depth. Catalog definition
and family searches, and global Product Content search, expose a 500-character
maximum. Scope, status, approval, source, entity-type, formula-kind, library,
score-type, clone-name/slug, and Inventory string filters match their associated
enum or persistence-column sizes. Legacy integer offsets have a finite
compatibility ceiling of 1,000,000; cursor pagination remains preferred for
large traversals. Sort orders, revisions, and event cursors have explicit
storage-compatible technical maxima.

## Reviewed residual behavior and controls

- User-authored regex validation and normalization use the timeout-capable
  `regex` engine with a 50 ms execution deadline. Pattern create and update use
  the same compiler validation.
- Python/Starlette JSON parsing resolves repeated object keys before Pydantic
  field validation. The application therefore follows the parser's last-key
  behavior. Internet-facing gateways should reject duplicate JSON keys if their
  security policy or signature model interprets them differently.
- Inventory balance mutation validates the resulting stored quantity against
  PostgreSQL `integer` capacity while the destination row is locked and before
  persistence.
- Stable ASCII code generation preserves existing behavior. Display text is
  Unicode, but an automatically generated code still needs at least one
  transliterable ASCII character unless the caller supplies an explicit valid
  code/slug.

## Verification

Collected boundary tests cover:

- exact encoded JSON size and one byte over;
- exact nesting limit and one level over;
- array, node, key, and key-length overflow;
- finite-number and cycle rejection;
- all major JSON-bearing request families;
- exact and over-limit bulk collections;
- multi-byte and combining-character string behavior;
- exact and over-limit description, prompt, note, and cursor behavior;
- null, empty, and repeated-field parser behavior;
- ORM-sized strings, Decimal precision, and database Integer bounds;
- persistence-sized public query filters;
- the exact 1,000,000 legacy-offset ceiling and one-over rejection;
- destination-balance overflow rejection before persistence;
- oversized cursor rejection before decode;
- emitted JSON structural and collection constraints.

`backend/scripts/generate_contract_reports.py` regenerates the machine-readable
request inventory. It resolves nullable and nested schemas, separates request
and response reachability, includes query parameters and route usage, and emits
risk tiers and reasons deterministically. Structural `x-max-json-*` extensions,
finite enum/pattern languages, UUID/date-time formats, and Decimal unions are
classified according to their effective bounds instead of being reported as
false-positive unbounded fields.
