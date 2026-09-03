# Product Attribute System

## Purpose

The Product Attribute System is the configurable PIM layer of Catalog. Catalog
remains the Product Master; the subsystem adds typed technical values, layouts,
filters, compatibility metadata, review state, history, and delta synchronization.
It has no dependency on Inventory or Pricing.

## Architecture

The implementation follows the established Catalog service/repository pattern:

- `attribute_models.py` contains the additional ORM entities.
- `AttributeDefinition` and `CategoryAttribute` extend the existing canonical
  models rather than introducing parallel definitions or assignments.
- `attribute_repository.py` owns queries, mutation, locking-ready access, and
  flushes. It never commits.
- `attribute_service.py` owns validation, normalization, transactions, history,
  and change events.
- `routers/product_attributes.py` exposes the versioned API and minimal admin UI.
- `attribute_validation.py` is HTTP-independent and deterministic.

## Entities

- Attribute Group: configurable display grouping and ordering.
- Attribute Definition: identity, scope, typed storage, display, validation,
  filtering, compatibility, and AI metadata.
- Category Attribute: direct category assignment and assignment-level overrides.
- Attribute Option and Alias: canonical enum choices and normalized synonyms.
- Normalization Rule: ordered deterministic transformations.
- Product Attribute Value: raw, canonical, display, typed projections, source,
  validation, approval, confidence, and soft-delete state.
- Product Attribute Value History: append-only value audit.
- Attribute Change Event: append-only sequence-backed delta feed.

## Storage kinds

- `CORE_FIELD`: read-only projection of Product identity fields.
- `RELATION`: read-only projection of an authoritative Catalog relation/value.
- `CATEGORY_PATH`: read-only derivation from the Category hierarchy.
- `ATTRIBUTE_VALUE`: dynamic typed Product Attribute Value.
- `CONTENT_FIELD`: dynamic value explicitly marked for later Product Content
  integration.

Core, relation, and category-path attributes cannot be written through the
dynamic value endpoint. This prevents duplicate sources of truth.

## Category inheritance and ordering

Global and system definitions apply to all categories. Category definitions are
resolved from the root-to-leaf category chain. If an attribute is assigned at
multiple levels, the deepest active assignment wins.

The deterministic order is:

1. attribute group `sort_order`;
2. winning category assignment `position`, when present;
3. definition `default_sort_order`;
4. definition `slug`.

Bulk reorder requests reject duplicate IDs and execute transactionally.

## Normalization and validation

Normalization happens before persistence and before any future AI fallback.
The validator supports whitespace cleanup, exact/case-insensitive/regex rules,
typed numeric and Boolean parsing, URL/date/datetime/JSON parsing, enum aliases,
units, ranges, lengths, regex validation, required values, forbidden values, and
multi-enum canonicalization.

Each result contains raw and canonical values, display value, normalized unit,
status, messages, applied rules, and typed projections. Invalid values are
rejected by default; callers may explicitly retain them for review.

## Approval and history

Values carry `DRAFT`, `PENDING_REVIEW`, `APPROVED`, or `REJECTED` state.
Creation, update, approval, rejection, normalization, and deactivation produce
append-only history. Authentication is not present yet, so actor identifiers are
optional caller-supplied audit metadata.

## Filtering and compatibility

Category filter metadata uses the same resolved layout and exposes configured
type, unit, enum options, configured ranges, and selection behavior.
Compatibility metadata exposes marked attributes and priorities only; it does
not implement compatibility calculations.

Observed range aggregation is intentionally not performed per request. Future
caching/materialization points are category resolved layouts, filter statistics,
and dashboard aggregates.

## Change events

Relevant writes add an event in the same database transaction. PostgreSQL
identity cursors give stable monotonic ordering independent of timestamps.
`GET /api/v1/catalog/attribute-changes` supports cursor, limit, product, and
entity filters. Rolled-back writes leave neither value changes nor false events.

## API overview

Administration CRUD is available under `/api/v1/catalog` for groups,
definitions, assignments, options, aliases, normalization rules, and product
values. Read contracts include resolved category layouts, Product layouts,
filters, compatibility metadata, history, delta changes, dashboard metrics, and
Product export.

The Product export contains Product identity, Category path, ordered attributes,
and the current attribute cursor. It contains no Inventory or Pricing data.

## Browser administration

`/api/v1/catalog/attribute-admin` provides a minimal server-served interface for
dashboard metrics, group and definition management entry points, category
layout inspection, Product attribute inspection, and review summaries. It uses
the same API and validation services. Access currently follows the application's
existing unauthenticated security state.

## Global seed

`python -m app.modules.catalog.seed_attributes` and
`POST /api/v1/catalog/attribute-seed` reconcile five Serbian display groups and
25 stable global/system definitions. Repeated execution creates no duplicates
and corrects authoritative storage mappings.

## Known limitations and future integration

- Missing-required Product counts are not calculated live because doing so is
  expensive; the dashboard returns `null` until a materialized/query strategy is
  introduced.
- The minimal admin page is functional but is not a full design-system frontend.
- Units are normalized but only configured rules perform conversions.
- Actor identity is not trusted until authentication exists.
- AI prompts are stored metadata only; the future AI module will consume them.
- `CONTENT_FIELD` values are ready for future Product Content ownership.
- Change events are ready for a future Webshop Publishing connector.
- Compatibility metadata is ready for a future Compatibility Engine/PC Builder.

## Enterprise platform completion

### Templates

Attribute Templates store reusable ordered sets of definitions, optional family
membership, required overrides, activation, and versions. Templates can inherit
from one parent, be cloned, exported/imported as validated JSON contracts, and
be assigned to or unassigned from Categories in bulk. Import and assignment are
atomic. Assignment materializes normal Category Attribute records so all
existing layout and inheritance behavior remains canonical.

### Families

Attribute Families provide reusable semantic groupings such as Storage,
Motherboards, Cooling, or GPU. Ordered family items reference existing
definitions. Families can be associated with Categories and Templates and
expose usage statistics. They do not replace display-oriented Attribute Groups.

### Formula and derived attributes

Formula and derived definitions share `AttributeFormula` with an explicit
`FORMULA` or `DERIVED` kind. Expressions use a restricted arithmetic grammar:
numeric constants, named attribute API identifiers, arithmetic operators, and
`min`, `max`, `round`, or `abs`. Attribute access, imports, comprehensions,
subscripts, and arbitrary calls are rejected.

The formula engine validates dependencies and rejects graph cycles. It supports
preview and Product recalculation. Successful source writes automatically
recalculate reachable targets in the same transaction, producing normal value
history and change events.

### Dependencies

Dependency rules link source and target definitions with `VISIBILITY`,
`ALLOWED_VALUES`, `REQUIRED`, or `DERIVATION` behavior and validated JSON
configuration. Product validation currently enforces required and allowed-value
rules. Visibility metadata is stored for administration and future client
rendering.

### Locking

Product Attribute Values may be locked with actor, timestamp, and reason.
Locked values reject Manual, AI, Import, and API overwrites until an explicit
unlock. Lock/unlock operations increment versions and create history/change
events, protecting approved administrator values from future automation.

### Prompt management

Prompt versions store extraction, normalization, and validation prompts plus
positive, negative, normalization, and validation examples. Version numbers are
monotonic per definition. Activation updates the definition's current prompt
metadata; prior versions remain append-only and can be diffed or reactivated.
No AI execution occurs in Catalog.

### Enterprise bulk editor and usage

The cross-Product bulk API supports preview and atomic commit. Every item is
validated before transaction completion; any failure rolls back all values,
history, derived recalculations, and change events.

Definition usage reports Product, Category, Template, Family, value, approved,
missing-required, and invalid counts. Dashboard metrics include all enterprise
entities and locked values.
