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