# AI-Cenovnici Database Design

## Overview
This document outlines the database schema design for AI-Cenovnici, a product catalog management system with supplier price list import capabilities, AI-powered content generation, and comprehensive administrative interface.

## Database Schema

### Core Tables

#### 1. Categories
```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_category_id INTEGER REFERENCES categories(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. Manufacturers
```sql
CREATE TABLE manufacturers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    website VARCHAR(255),
    contact_person VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3. Suppliers
```sql
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    website VARCHAR(255),
    payment_terms TEXT,
    currency_code CHAR(3) DEFAULT 'EUR', -- ISO 4217 currency code
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4. Products
```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL, -- Stock Keeping Unit
    name VARCHAR(500) NOT NULL,
    description TEXT,
    short_description VARCHAR(255),
    category_id INTEGER REFERENCES categories(id),
    manufacturer_id INTEGER REFERENCES manufacturers(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    ean VARCHAR(50), -- European Article Number
    weight DECIMAL(10,3),
    dimensions VARCHAR(50), -- e.g., "10x20x30 cm"
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 5. Product Specifications (JSONB)
```sql
CREATE TABLE product_specifications (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    specifications JSONB NOT NULL, -- Category-specific structured technical specs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 6. Product Prices
```sql
CREATE TABLE product_prices (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id),
    manufacturer_id INTEGER REFERENCES manufacturers(id),
    purchase_price DECIMAL(12,4),
    currency_code CHAR(3) DEFAULT 'EUR',
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    retail_price DECIMAL(12,4),
    stock_quantity INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 7. Pricing Rules
```sql
CREATE TABLE pricing_rules (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    manufacturer_id INTEGER REFERENCES manufacturers(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    product_id INTEGER REFERENCES products(id),
    margin_percentage DECIMAL(5,2),
    min_price DECIMAL(12,4),
    max_price DECIMAL(12,4),
    price_calculation_type VARCHAR(50) DEFAULT 'margin', -- 'margin', 'fixed', 'percentage'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 8. AI Prompt Templates
```sql
CREATE TABLE ai_prompt_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    template_type VARCHAR(50) NOT NULL, -- 'description', 'specification', 'translation', 'classification'
    prompt TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 9. Price History (Version Control)
```sql
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    product_price_id INTEGER REFERENCES product_prices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id),
    supplier_id INTEGER REFERENCES suppliers(id),
    purchase_price DECIMAL(12,4),
    currency_code CHAR(3) DEFAULT 'EUR',
    discount_percentage DECIMAL(5,2) DEFAULT 0,
    retail_price DECIMAL(12,4),
    stock_quantity INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 10. Audit Log
```sql
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER, -- If using authentication system
    action VARCHAR(100) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 11. Import Sessions
```sql
CREATE TABLE import_sessions (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(id),
    file_path VARCHAR(500),
    file_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    total_records INTEGER DEFAULT 0,
    imported_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Supplier Data Quality, Validation and Change Tracking

#### 1. Raw Data Preservation
Every imported supplier record must be preserved exactly as received:
- supplier product code
- supplier EAN
- supplier name
- supplier description
- supplier price
- stock
- currency
- source file or API response
- import timestamp
- import batch

#### 2. EAN Validation
- Detect invalid length (EAN-13 must be exactly 13 digits)
- Validate EAN-13 checksum using standard algorithm
- Detect values such as 111111, 123456, repeated digits and obvious placeholders
- Detect missing EAN values
- If supplier EAN has 12 digits, test whether adding a leading zero produces a valid EAN-13
- Never overwrite the original supplier EAN in the import record
- Store normalized EAN separately (e.g., with leading zeros for 12-digit inputs)
- Store validation status, confidence score and validation message
- Create a review queue for suspicious EAN values requiring manual verification

#### 3. Supplier Product Code Validation
- Supplier product codes are not permanently unique across suppliers or time periods
- Detect when the same supplier reuses an existing code for a significantly different product
- Compare manufacturer, model, EAN, name and category to identify potential conflicts
- Create an alert and require manual review before remapping conflicting codes
- Preserve complete code history with timestamps to track when each code was assigned

#### 4. Price History and Anomaly Detection
- Store every observed supplier price with timestamp for comprehensive audit trail
- Support daily price history tracking
- Detect sudden price increases or decreases using configurable thresholds
- Allow configurable percentage and absolute-value thresholds for anomaly detection
- Create alerts for suspicious price changes requiring review
- Distinguish real price changes from currency, VAT or unit errors through validation logic

#### 5. Description History
- Preserve every supplier description version with timestamp
- Detect significant description changes using content comparison algorithms
- Show old and new descriptions side by side in the admin interface
- Create an alert when a description changes substantially (threshold-based)
- Never use supplier descriptions as the preferred source when an official manufacturer description exists

#### 6. Description Source Priority
1. Official manufacturer page
2. Official manufacturer PDF or data sheet
3. Trusted distributor or supplier description
4. AI-generated description based only on verified specifications
5. Manual description

#### 7. Missing Content Workflow
- Create a review list for products without descriptions requiring manual input
- Create a review list for products without EAN values needing verification
- Create a review list for products without official manufacturer source
- Allow manual completion of missing content through the browser admin interface

#### 8. Supplier Import Configuration
- Each supplier can have multiple import connectors
- Supported connector types: API, XML, Excel, CSV, JSON, ZIP and manual upload
- Suppliers may change import method over time
- Preserve connector configuration history for audit trail
- Allow activating and deactivating connectors without deleting previous configurations
- Parsing and column mapping must be configurable from the browser where possible

#### 9. Alerts and Review Queues
- Invalid EAN values
- Missing EAN entries
- Reused supplier codes with conflicting products
- Large price changes requiring verification
- Changed descriptions requiring review
- Missing official description content
- Unmapped product entries
- Low-confidence mapping results
- Changed category or manufacturer assignments
- Import schema changes requiring attention

#### 10. Design Principle
Raw supplier data is immutable.
Normalized and corrected data is stored separately.
Corrections must always be traceable to the original imported value.

## Table Relationships

1. **Categories** - Self-referencing (parent-child relationships for hierarchical categories)
2. **Manufacturers** - Related to Products via manufacturer_id
3. **Suppliers** - Related to Products and Product Prices via supplier_id
4. **Products** - 
   - Related to Categories (many-to-one)
   - Related to Manufacturers (many-to-one) 
   - Related to Suppliers (many-to-one)
   - Has one-to-many relationships with:
     - Product Specifications
     - Product Prices
     - Price History
5. **Product Specifications** - One-to-many with Products, many-to-one with Categories
6. **Product Prices** - 
   - One-to-many with Products
   - Many-to-one with Suppliers and Manufacturers
7. **Pricing Rules** - Can be applied to categories, manufacturers, suppliers, or specific products
8. **Price History** - Links to Product Prices for version control
9. **Audit Log** - Tracks all database changes across all tables

## JSONB vs Relational Columns

### JSONB Columns:
1. `product_specifications.specifications` - Category-specific structured technical specifications that vary by category type
2. `audit_log.old_values` and `audit_log.new_values` - Flexible storage for change tracking 
3. `price_history` - For storing historical values in a flexible format

### Relational Columns:
All other columns are defined with specific data types to ensure data integrity, constraints, and proper indexing.

## Key Design Decisions

1. **Hierarchical Categories**: Using self-referencing foreign keys for parent-child category relationships
2. **Flexible Specifications**: JSONB storage for product specifications to accommodate different category requirements
3. **Version Control**: Separate history table for price changes to maintain audit trail
4. **Modular Pricing Rules**: Rules can be applied at multiple levels (category, manufacturer, supplier, product)
5. **Import Tracking**: Dedicated import sessions table to track supplier data imports
6. **Data Quality and Validation**: Comprehensive requirements for maintaining data integrity during supplier imports

## Catalog Standardization and Panteon Preparation

### 1. Panteon role
- Panteon assigns the final internal product code after import
- AI-Cenovnici prepares and validates the import table before Panteon import
- supplier product codes must not be used as the main internal product identity
- after successful Panteon import, the assigned Panteon internal code must be stored and linked to the canonical product

### 2. New product workflow
- imported supplier records are first checked against existing canonical products
- matched products are linked to the existing canonical product and existing Panteon code
- unmatched products enter a new-product preparation queue
- new products must be categorized, standardized, validated and approved before export to Panteon

### 3. Internal category system
- supplier categories are only source data and must never directly become internal categories
- maintain an internal hierarchical category tree
- products should be assigned to the most specific valid internal category
- supplier category mappings may be stored as hints, but product-level evidence has priority
- example: a supplier may place monitor mounts in Monitors, while the internal category is Monitor Mounts

### 4. Category classification
- classification should use supplier name, description, manufacturer, MPN, EAN, specifications and previous mapping knowledge
- return proposed category, confidence score and explanation
- high-confidence classifications may be automatically accepted according to configurable thresholds
- uncertain classifications must enter a manual review queue
- manual corrections must be stored as reusable classification knowledge

### 5. Category-specific attributes
- every internal category can define required and optional product attributes
- attributes must be configurable from the browser
- examples include capacity, power, memory type, frequency, connector, panel type, screen size, color, warranty and package quantity
- products missing required attributes must not be marked ready for Panteon export unless explicitly overridden

### 6. Standardized product names
- do not use supplier product names as final internal product names
- generate product names according to category-specific naming templates
- templates and attribute order must be configurable from the browser
- naming must use only verified product data
- do not invent specifications or marketing claims
- preserve supplier names separately for traceability

### 7. Naming examples
- memory: Memorija {Type} {Capacity} {Manufacturer} {Series} {Speed}MHz {Latency} {Kit} {Color} {MPN}
- power supply: Napajanje {Power}W {Manufacturer} {Series} {Efficiency} {Modularity} {Color} {MPN}
- SSD: SSD {Capacity} {FormFactor} {Interface} {Manufacturer} {Series} {MPN}
- monitor: Monitor {ScreenSize} {Resolution} {PanelType} {RefreshRate}Hz {Manufacturer} {Model}

### 8. Naming rule behavior
- omit unavailable optional values cleanly
- prevent duplicated words and values
- normalize units and formatting
- support category-specific abbreviations
- support required prefixes and suffixes
- allow previewing the generated name before approval
- maintain naming rule versions and name history

### 9. Panteon export preparation
- generate a configurable export table for new products
- support Excel and CSV export initially
- export fields and column order must be configurable
- store every generated export batch
- store which products were included
- store export status, creation time, user and file version
- prevent accidental duplicate export of the same approved new product

### 10. Panteon import reconciliation
- after Panteon assigns internal product codes, allow importing a result file
- match returned Panteon codes to the exported records
- validate that every exported product received a code
- flag missing, duplicated or conflicting returned codes
- store the final Panteon code on the canonical product
- preserve reconciliation history

### 11. Product readiness statuses
- imported
- validation_required
- mapping_required
- category_required
- attributes_required
- naming_required
- review_required
- ready_for_panteon
- exported_to_panteon
- panteon_code_assigned
- rejected

### 12. Review interface
- show original supplier data
- show proposed internal category
- show extracted attributes
- show generated standardized name
- show confidence and validation warnings
- allow correction before approval
- allow bulk approval only when there are no critical warnings

### 13. Design principle
Supplier data is evidence.
Internal category, standardized name and Panteon identity are controlled company data.
Every transformation from supplier data to internal product data must be explainable and traceable.

## Category-Specific Attributes, Data Normalization and Presentation Rules

### 1. Category isolation:
- every internal category must have its own attribute definitions
- every category must have its own naming fields
- every category must have its own specification fields
- every category must have its own SEO fields
- every category must have its own landing page fields
- every category must have its own filter fields
- fields from unrelated categories must not appear or be mixed
- shared attributes may exist only through explicitly configured reusable definitions

### 2. Structured attribute definitions:
Each category attribute must support:
- internal key
- Serbian display name
- optional English name
- data type
- unit
- required or optional status
- allowed values
- minimum and maximum values
- decimal precision
- sort order
- whether it is used in product name
- whether it is used in specifications
- whether it is used in filters
- whether it is used in SEO
- whether it is used in landing pages
- whether it is used in comparison
- whether it is visible in Panteon export
- whether it can have multiple values

### 3. Separate raw, normalized and display values:
- preserve the original raw value exactly as received
- store a normalized machine-readable value separately
- store the canonical unit separately
- generate display values according to configurable formatting rules
- never overwrite raw imported values
- every normalization must be traceable to its source rule

### 4. Unit normalization:
- normalize equivalent representations into one canonical value
- examples:
  - 4600 MHz, 4600MHz and 4.6 GHz may represent the same frequency depending on category and attribute
  - 1000 GB may be normalized according to configured business rules
  - 0.5 TB and 500 GB must not be treated as equal unless the category rules explicitly define the conversion
- conversions must be category-aware
- the same unit conversion must not automatically apply to unrelated attributes
- store the original unit, normalized unit and conversion rule used

### 5. Category-specific formatting:
- formatting rules must be configurable separately for every category and attribute
- examples:
  - processor frequency display: 4.6GHz
  - memory frequency display: 4600MHz
  - power supply wattage: 850W
  - storage capacity: 1TB
  - screen size: 27"
  - refresh rate: 180Hz
- support rules for spaces between value and unit
- support decimal separator rules
- support decimal precision
- support uppercase and lowercase unit notation
- support prefixes, suffixes and abbreviations

### 6. Context-specific presentation:
The same normalized attribute may have different display templates for:
- product name
- specification table
- webshop filter
- SEO title
- SEO description
- landing page
- product comparison
- Panteon export

Example:
- normalized value: 4600
- unit: MHz
- product name: 4600MHz
- specification table: 4600 MHz
- filter label: 4600MHz

### 7. Value dictionaries and controlled vocabulary:
- attributes such as color, modularity, panel type, socket and efficiency rating must use controlled values
- map supplier variants and aliases to one internal value
- examples:
  - Black, Crna, BK and BLK map to Crna
  - Full Modular, Fully Modular and Modularno map to Potpuno modularno
  - IPS-level and IPS must remain separate when technically different
- preserve supplier value and selected internal value
- mappings must be configurable through the admin interface

### 8. Validation rules:
- validate data type
- validate unit
- validate allowed values
- validate ranges
- detect impossible or suspicious values
- detect inconsistent values between attributes
- examples:
  - memory frequency written as 4.6GHz should be convertible to 4600MHz when rules permit
  - CPU frequency written as 4600MHz may be displayed as 4.6GHz
  - an 8500W consumer power supply should trigger a warning
  - refresh rate of 0Hz should trigger a warning
- warnings and critical errors must enter review queues

### 9. Missing and conflicting values:
- indicate required missing attributes
- preserve values from all sources
- select a preferred verified value according to source priority
- create a conflict alert when trusted sources disagree
- allow manual selection of the canonical value
- store reviewer, reason and decision history

### 10. Category-specific content fields:
- specification fields, SEO fields and landing page fields must be configurable per category
- landing page sections may include:
  - headline
  - subtitle
  - feature blocks
  - benefit blocks
  - image sections
  - video sections
  - technical highlights
  - FAQ
  - call to action
- categories may define which sections are available and required
- content templates must use only category-relevant attributes

### 11. Rule versioning:
- attribute definitions must have versions
- normalization rules must have versions
- formatting rules must have versions
- controlled-value mappings must have versions
- products must retain which rule version produced each normalized or displayed value
- changing a rule must allow previewing affected products before recalculation

### 12. Bulk normalization:
- allow recalculating normalized values and displays for an entire category
- show a preview of old and new values
- allow applying changes only to selected products
- never destroy original source data or manual corrections

### 13. Design principle:
Store data in a structured and canonical form.
Presentation is generated from configurable category-specific rules.
The same attribute may be displayed differently in product names, specifications, filters, SEO and landing pages without duplicating the underlying value.

## Indexes and Constraints

```sql
-- Performance indexes
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_manufacturer ON products(manufacturer_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_product_prices_product ON product_prices(product_id);
CREATE INDEX idx_product_prices_supplier ON product_prices(supplier_id);
CREATE INDEX idx_price_history_product ON price_history(product_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);