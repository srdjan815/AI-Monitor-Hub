# Product Content Platform

## Purpose and boundary

Product Content is the CMS layer for customer-visible, marketing, descriptive,
SEO, campaign, document, and video-reference information. Catalog remains the
Product Master and Product Attributes remain the technical specification
engine. Product Content references Catalog Product IDs and does not import
Inventory, Supplier, Pricing, Import, Scraper, Media Processing, AI execution,
or Publishing modules.

## Architecture

The module follows the existing ORM/repository/service/router/schema layout.
Repositories query and flush; services own validation and transactions. Every
relevant write creates a sequence-backed delta event in the business
transaction.

The top-level `router.py` is an aggregator. Focused transport-only routers live
under `routers/` for Languages, Content Types, Product Content, SEO, Landing
Pages, Documents, Videos, Library, Templates, Preview, Scoring, Prompts, Usage,
Search, and Admin. They perform dependency injection and service invocation;
they do not construct SQL or own transactions.

`repositories.py` is the canonical query/persistence boundary. Responsibility-
specific service classes coordinate configuration, immutable revisions,
references, reusable content, templates, prompts, preview, scoring, and
search/export. `repository.py` and `service.py` retain compatibility names
without duplicating implementations.

## Model

- `Language`: unlimited normalized languages; Serbian is the idempotent default.
- `ContentType`: configurable ordered rich-text/multilanguage content roles.
- `ProductContent`: immutable logical revisions with title, body, summary,
  workflow, source provenance, actors, AI metadata, content hash, and duplicate
  reference.
- `ProductSEO`: language-specific version-ready SEO, robots, Open Graph,
  Twitter Card, and Schema.org metadata.
- `LandingPage`: language/campaign content with body, hero, CTA, metadata,
  status, approval, and revision identity.
- `DocumentReference`: URL-only references; no media processing.
- `VideoReference`: ordered URL/thumbnail references; no media processing.
- `ContentChangeEvent`: monotonic cursor for future publishing synchronization.
- `ContentLibraryItem` and `ContentLibraryRevision`: reusable Blocks, Snippets,
  and Sections with category, tags, workflow state, visibility, and history.
- `ProductLibraryReference`: ordered Product usage of reusable library items.
- `ContentTemplate`, `ContentTemplateItem`, and
  `ContentTemplateCondition`: versioned compositions with normalized ordering
  and AND/OR/NOT Product-field or Product-Attribute conditions.
- `ProductContentTemplate`: normalized Product/template assignments.
- `ContentScoringPolicy` and `ContentScoreHistory`: configurable weights,
  mandatory sections, and retained Content/SEO scores.
- `ContentTypePromptVersion`: versioned prompt metadata without AI execution.

Structured metadata uses JSONB only for appropriate extensible structures; core
domain fields are normalized columns.

## Versioning and workflow

Product Content updates never overwrite a row. The current row is retired and a
new revision is created. Rollback copies a historical revision into a new Draft
revision, preserving the full chain.

Allowed transitions are explicit: Draft, Waiting Review, Approved, Rejected,
Published, and Archived. Approval/publishing actors and timestamps are retained.

## Source and AI metadata

Sources support Manual, AI, Supplier, Manufacturer, Scraper, ERP, Import, API,
and System values while retaining references and structured metadata. Prompt,
model, temperature, tokens, confidence, generation duration, reason, and notes
are metadata only. This module never executes AI.

## Search, score, export, and delta

Current content can be filtered by Product, Language, Content Type, status,
approval, source, and pagination. Content Score reports descriptions, SEO,
landing pages, documents, videos, and translations as a percentage.

Configurable policies replace equal weighting and retain score history. SEO
scoring checks field presence, length, structured metadata, and duplicates.
Global search covers current Product Content, library items, and templates.
Reusable objects expose Product usage and last-use metadata.

The read-only export combines all CMS entities and score without Inventory,
Pricing, or publishing behavior. Delta consumers use a monotonic cursor rather
than timestamps.

## Browser administration

`/api/v1/content/admin` is the autonomous minimal administration surface for
types, languages, Product content, SEO, landing pages, references, approval,
history, rollback, preview, search, and dashboard entry points. Authentication
remains dependent on the application's current security state.

## Preview, scheduling, and references

Templates resolve built-in Product variables and technical attributes from the
Product Attribute Platform. Unknown variables remain visible and are returned
as validation output. Rendering supports Desktop, Tablet, Mobile, and Raw
preview metadata, language selection, and Draft/Published intent.

Content and Landing Pages retain publish/expiry scheduling metadata, campaign,
and priority. Documents and Videos retain last-check time, link status, error,
and next-check time. No scheduler, crawler, publisher, media processor, or AI
executor is included.

## Rendering and variable security

Stored source is preserved unchanged. Normal preview sanitizes active content:
script/object/embed elements, event-handler attributes, JavaScript/data HTML
URLs, and unapproved iframe sources are excluded. Interpolated values are HTML
escaped. Raw source output requires both `viewport=RAW` and the explicit
`trusted_raw=true` request flag; consumers must restrict that mode to trusted
administrators.

Variables use a constrained `{{Name}}` grammar. Product fields form an explicit
built-in namespace and Product Attribute variables use their canonical
`api_name`. Unknown and malformed variables are reported separately. Resolution
does not support Python attribute traversal, private names, imports, callables,
`eval`, or `exec`.

Template conditions are normalized rows, capped per item, and support only the
registered AND/OR/NOT and EQ/NE/GT/GE/LT/LE/EXISTS protocol constants. Numeric
comparisons fail closed when types cannot be converted. The condition model has
no parent/child references, so cycles cannot be represented.

## Intentional protocol constants

Workflow states and transitions, source identifiers, condition operators,
preview modes, link statuses, score types, built-in variable names, default
pagination limits, and SEO protocol limits are centralized in `constants.py`.
They remain code constants because changing them changes the API protocol.
Administratively variable data—Languages, Content Types, library categories,
tags, templates, prompt versions, and scoring weights—remains database-backed.

## Limitations and future consumers

- Document and Video references are URL records only.
- Duplicate detection is hash-based metadata, not NLP.
- Browser administration is a lightweight API-backed navigation surface.
- Supplier conditions intentionally remain a future consumer integration.
- Authentication and authorization remain application-level prerequisites.
- HTML sanitization is intentionally preview-scoped. A future Publishing
  consumer must apply its own channel-specific output policy.

Supplier, Import, Scraper, AI generation, Media Processing, and Publishing must
consume this platform rather than creating alternate content stores.

## Chapter 2 closure hardening

The HTTP layer delegates to focused service classes. Services own validation,
row locking, commit, rollback, and refresh; repositories own SQL and flush only.
Although those classes currently share `services.py`, they do not share hidden
transaction state. A physical package split was deliberately deferred because
it would move stable compatibility imports without reducing class
responsibilities.

Current revisions are protected by PostgreSQL partial unique indexes for
Product Content, SEO, and Landing Page business keys. Active prompt versions
are protected by a partial unique index per Content Type. Writers serialize on
the relevant parent/current row and translate integrity conflicts to domain
errors.

Stored source is not publishable output. Normal preview passes through the
central Bleach sanitizer and escapes resolved variables. Trusted raw preview is
disabled by default through
`PRODUCT_CONTENT_TRUSTED_RAW_PREVIEW=false`; a client flag cannot enable it.
Even when enabled operationally, the route remains an internal/admin surface
that requires a future authorization policy. Exports label their payload as
unsanitized stored source and explicitly mark it non-publishable. A future
Publishing consumer must use a channel-specific renderer and sanitizer.

All scheduled timestamps must include a timezone offset. PostgreSQL stores
timezone-aware values, and database checks enforce `publish_at < expire_at`
when both are present.
