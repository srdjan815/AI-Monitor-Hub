# Service and repository decomposition

## Decision

The public class names remain compatibility façades, but implementation
responsibilities are split by transaction and query domain. A façade owns no
business method and receives one SQLAlchemy session through the common support
base. This keeps existing imports stable while preventing a new generic base
service or a second transaction owner.

The invariant remains:

```text
router -> command service/coordinator -> repository -> PostgreSQL
                  |
                  +-> commit / rollback / refresh
```

Repositories add, mutate, lock, query, and flush. They never commit or raise
HTTP exceptions. Services validate and own the final transaction. Routers do
not construct SQL or call session persistence methods.

## Before and after

| Compatibility surface | Pre-change | Final façade | Largest implementation | Responsibility split |
|---|---:|---:|---:|---|
| `CatalogService` | 725 LOC / 22 methods | 18 LOC | `CategoryService` | category, legacy attribute/type façade, product |
| `CatalogRepository` | 462 LOC / 33 methods | 18 LOC | `LegacyAttributeRepository` | category, legacy attribute, product |
| `InventoryService` | 1,040 LOC / 38 methods | 22 LOC | `ReservationService` 398 LOC | support, balance/warehouse, movement, reservation |
| `InventoryRepository` | 423 LOC / 32 methods | 25 LOC | `WarehouseBalanceRepository` | balance/warehouse, movement, reservation |
| `AttributePlatformService` | 892 LOC / 43 methods | 34 LOC | `AttributeTemplateService` 312 LOC | family, template, formula, dependency, prompt, usage, value mutation |
| `ProductAttributeService` | 822 LOC at audit; 809 LOC after query extraction | 25 LOC | `ProductAttributeValueService` 325 LOC | support, definition/group, category assignment, option/rule, value |
| `ProductAttributeRepository` | 371 LOC at audit; 697 LOC after platform completion | 31 LOC | `AttributeDefinitionRepository` 276 LOC | support/dashboard, definition/query, assignment, option/rule, value/history, platform |
| `ContentRepository` | 619 LOC at audit; 889 LOC immediately before split | 21 LOC | `ScoringRepository` 303 LOC | support, configuration, revision/reference, library/template, scoring/prompt |
| Product Content service file | 1,226 LOC / seven service classes | 30 LOC export façade | `ReferenceService` 323 LOC | support, configuration, revision, reference, library, template, prompt |

LOC values are physical source lines and are intended as cohesion evidence, not
as an independent quality target. Automated decomposition tests cap each new
implementation file at 350 lines and verify disjoint responsibilities.

## Catalog

`CatalogService` and `CatalogRepository` preserve the original import paths.
Category mutations, Product mutations, and the legacy Attribute
Definition/Attribute Type façade have separate implementations. Catalog remains
the only owner of the `Product` ORM class.

## Product Attributes

`ProductAttributeService` composes:

- `AttributeDefinitionService`;
- `CategoryAttributeService`;
- `AttributeOptionService`;
- `ProductAttributeValueService`.

`ProductAttributeRepository` composes matching definition, assignment, option,
value, and platform repositories. `AttributeQueryService` remains the bounded
read model for resolved layouts. `AttributeMutationCoordinator` remains the
only route-facing entry point for base writes that trigger derived
recalculation. All composed objects resolve to one repository session.

## Inventory

Warehouse/balance, movement, and reservation operations are separate. The
reservation service remains the transaction owner for reserve, release,
cancel, expire, and fulfill operations so balance, movement, and reservation
state cannot commit independently.

## Product Content

Configuration, immutable revisions, references, reusable library content,
templates, prompts, and scoring queries are separate service/repository
domains. `services.py` and `repositories.py` only re-export or compose the
canonical implementations. Revision rollback and template clone remain within
their respective single service transaction.

## Enforcement

The following collected tests guard the split:

- `test_catalog_decomposition.py`;
- `test_inventory_decomposition.py`;
- `test_attribute_platform_decomposition.py`;
- `test_product_attribute_decomposition.py`;
- `test_product_content_decomposition.py`;
- `test_module_boundaries.py`.

An intentional exception requires a non-empty reason in
`ARCHITECTURE_EXCEPTIONS` and a matching architecture decision record. Empty or
silent exceptions are not accepted.
