# Module boundaries

AI Monitor Hub is not an ERP. The external ERP remains the accounting and
operational system of record. AI Monitor Hub imports and normalizes supplier
offers, matches them to the internal catalog, enriches product content,
calculates prices, and publishes selected data.

## Canonical data and dependency direction

Catalog is the canonical internal product master. Supplier feeds describe
supplier offers, including supplier availability and purchase prices.
Supplier availability is feed data; it is not internal warehouse inventory.
Pricing uses supplier offers and pricing rules, not Inventory movements or
ERP documents.

```text
Source Connectors
        |
        v
Supplier Feeds
        |
        v
Import / Normalization
        |
        v
Product Matching
        |
        v
Catalog
   |        |        |
   v        v        v
Pricing   AI Enrichment   Media
   |
   v
Publishing / ERP Sync

Optional downstream module:

Catalog
   |
   v
Inventory
```

Inventory may reference Catalog products by `product_id`. This is the only
allowed dependency between those two modules: Catalog must never import or
require Inventory. Product creation, matching, enrichment, pricing, and
publishing must work without warehouses, balances, movements, or
reservations.

## Prohibited coupling

- Supplier Feed and Import must not create balances, movements, or
  reservations.
- Product Matching must use supplier and Catalog data, not stock quantities.
- Pricing must not depend on Inventory, movements, reservations, purchasing,
  goods receipts, or accounting records.
- AI Enrichment, Scraper, Media, Publishing, and ERP Sync must not depend on
  Inventory.
- Inventory must not point back to Supplier Feed, Import, Matching, Pricing,
  AI Enrichment, Media, Publishing, or ERP Sync.
- No future core module may require Inventory without an explicit
  architecture decision.
- AI Monitor Hub must not implement procurement, sales, invoices, purchase
  orders, goods receipts, delivery notes, or accounting documents.

Inventory remains an isolated, optional downstream capability retained for
backward compatibility. Its API and migrations remain available, but its
records are never prerequisites for the primary workflow.
