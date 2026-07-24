\set ON_ERROR_STOP on

INSERT INTO categories (
    name, code, parent_id, position, is_active, version, id, created_at, updated_at
)
VALUES
    (
        'Benchmark Parent',
        'benchmark-parent',
        NULL,
        0,
        TRUE,
        1,
        md5('benchmark-category-parent')::uuid,
        '2026-01-01 00:00:00+00',
        '2026-01-01 00:00:00+00'
    ),
    (
        'Benchmark Child',
        'benchmark-child',
        md5('benchmark-category-parent')::uuid,
        0,
        TRUE,
        1,
        md5('benchmark-category-child')::uuid,
        '2026-01-01 00:00:01+00',
        '2026-01-01 00:00:01+00'
    )
ON CONFLICT DO NOTHING;

INSERT INTO warehouses (
    code, name, description, is_active, version, id, created_at, updated_at
)
VALUES
    (
        'BENCH-A',
        'Benchmark Warehouse A',
        'Disposable final-validation warehouse',
        TRUE,
        1,
        md5('benchmark-warehouse-a')::uuid,
        '2026-01-01 00:00:00+00',
        '2026-01-01 00:00:00+00'
    ),
    (
        'BENCH-B',
        'Benchmark Warehouse B',
        'Disposable final-validation warehouse',
        TRUE,
        1,
        md5('benchmark-warehouse-b')::uuid,
        '2026-01-01 00:00:01+00',
        '2026-01-01 00:00:01+00'
    )
ON CONFLICT DO NOTHING;

INSERT INTO products (
    category_id,
    name,
    code,
    sku,
    status,
    is_active,
    version,
    id,
    created_at,
    updated_at
)
SELECT
    md5('benchmark-category-child')::uuid,
    'Benchmark Product ' || number,
    'benchmark-product-' || number,
    'BENCH-SKU-' || number,
    'ACTIVE',
    TRUE,
    1,
    md5('benchmark-product-' || number)::uuid,
    '2026-01-01 01:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 01:00:00+00'::timestamptz
        + number * interval '1 millisecond'
FROM generate_series(1, 100000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO inventory (
    warehouse_id,
    product_id,
    quantity_on_hand,
    quantity_reserved,
    minimum_stock,
    reorder_point,
    version,
    is_active,
    id,
    created_at,
    updated_at
)
SELECT
    md5('benchmark-warehouse-a')::uuid,
    md5('benchmark-product-' || number)::uuid,
    100,
    1,
    10,
    20,
    1,
    TRUE,
    md5('benchmark-inventory-' || number)::uuid,
    '2026-01-01 02:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 02:00:00+00'::timestamptz
        + number * interval '1 millisecond'
FROM generate_series(1, 100000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO inventory_movements (
    movement_number,
    movement_type,
    product_id,
    source_warehouse_id,
    destination_warehouse_id,
    quantity,
    external_reference,
    occurred_at,
    created_at,
    created_by,
    is_reversed,
    version,
    id
)
SELECT
    'BM' || lpad(number::text, 30, '0'),
    'RECEIPT',
    md5('benchmark-product-' || number)::uuid,
    NULL,
    md5('benchmark-warehouse-a')::uuid,
    100,
    'benchmark-movement-' || number,
    '2026-01-01 03:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 03:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    'final-validation',
    FALSE,
    1,
    md5('benchmark-movement-' || number)::uuid
FROM generate_series(1, 100000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO inventory_reservations (
    reservation_number,
    product_id,
    warehouse_id,
    quantity,
    fulfilled_quantity,
    status,
    external_reference,
    version,
    created_at,
    updated_at,
    id
)
SELECT
    'BR' || lpad(number::text, 30, '0'),
    md5('benchmark-product-' || number)::uuid,
    md5('benchmark-warehouse-a')::uuid,
    1,
    0,
    'ACTIVE',
    'benchmark-reservation-' || number,
    1,
    '2026-01-01 04:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 04:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    md5('benchmark-reservation-' || number)::uuid
FROM generate_series(1, 100000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO jobs (
    job_type,
    queue,
    priority,
    status,
    payload,
    attempt,
    max_attempts,
    available_at,
    correlation_id,
    idempotency_key,
    created_by,
    version,
    id,
    created_at,
    updated_at
)
SELECT
    'system.synthetic',
    CASE WHEN number % 20 = 0 THEN 'secondary' ELSE 'default' END,
    number % 10,
    CASE
        WHEN number % 10 = 0 THEN 'SUCCEEDED'
        WHEN number % 9 = 0 THEN 'RETRYING'
        ELSE 'PENDING'
    END,
    jsonb_build_object('duration_ms', 0),
    0,
    3,
    '2025-12-31 00:00:00+00',
    md5('benchmark-correlation-' || number)::uuid,
    'benchmark-job-' || number,
    'final-validation',
    1,
    md5('benchmark-job-' || number)::uuid,
    '2026-01-01 05:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 05:00:00+00'::timestamptz
        + number * interval '1 millisecond'
FROM generate_series(1, 100000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_groups (
    name, slug, description, sort_order, is_active, version, created_at, updated_at, id
)
SELECT
    'Benchmark Group ' || number,
    'benchmark-group-' || number,
    'Disposable final-validation group',
    number,
    TRUE,
    1,
    '2026-01-01 06:00:00+00',
    '2026-01-01 06:00:00+00',
    md5('benchmark-group-' || number)::uuid
FROM generate_series(1, 10) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_definitions (
    name,
    code,
    scope,
    data_type,
    description,
    validation_rules,
    api_name,
    is_required,
    is_visible,
    is_filterable,
    is_searchable,
    allows_multiple,
    is_active,
    version,
    id,
    created_at,
    updated_at,
    slug,
    internal_name,
    group_id,
    storage_kind,
    status,
    default_sort_order,
    show_in_admin,
    show_on_webshop,
    show_in_mini_specification,
    show_in_full_specification,
    is_compatibility_attribute,
    use_ai,
    accepted_units,
    filter_sort_order,
    compatibility_priority,
    confidence_threshold,
    examples,
    forbidden_values
)
SELECT
    'Benchmark Attribute ' || number,
    'benchmark_attribute_' || number,
    CASE
        WHEN number <= 5000 THEN 'GLOBAL'
        WHEN number <= 9000 THEN 'CATEGORY'
        ELSE 'SYSTEM'
    END,
    'TEXT',
    'Representative disposable attribute',
    '{}'::jsonb,
    'benchmark_attribute_' || number,
    FALSE,
    TRUE,
    number % 3 = 0,
    number % 5 = 0,
    FALSE,
    TRUE,
    1,
    md5('benchmark-attribute-' || number)::uuid,
    '2026-01-01 06:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 06:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    'benchmark-attribute-' || number,
    'benchmark_attribute_' || number,
    md5('benchmark-group-' || ((number - 1) % 10 + 1))::uuid,
    'ATTRIBUTE_VALUE',
    'ACTIVE',
    number,
    TRUE,
    TRUE,
    number % 7 = 0,
    TRUE,
    number % 11 = 0,
    FALSE,
    '[]'::jsonb,
    number,
    number % 100,
    0.8,
    '[]'::jsonb,
    '[]'::jsonb
FROM generate_series(1, 10023) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO category_attributes (
    category_id,
    attribute_id,
    position,
    is_active,
    version,
    id,
    created_at,
    updated_at
)
SELECT
    CASE
        WHEN number % 2 = 0
            THEN md5('benchmark-category-parent')::uuid
        ELSE md5('benchmark-category-child')::uuid
    END,
    md5('benchmark-attribute-' || number)::uuid,
    number,
    TRUE,
    1,
    md5('benchmark-assignment-' || number)::uuid,
    '2026-01-01 07:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 07:00:00+00'::timestamptz
        + number * interval '1 millisecond'
FROM generate_series(1, 10023) AS series(number)
WHERE number > 5000 OR number % 5 = 0
ON CONFLICT DO NOTHING;

INSERT INTO category_attributes (
    category_id,
    attribute_id,
    position,
    is_filter_override,
    is_active,
    version,
    id,
    created_at,
    updated_at
)
SELECT
    md5('benchmark-category-child')::uuid,
    md5('benchmark-attribute-' || number)::uuid,
    number,
    number % 3 = 0,
    TRUE,
    1,
    md5('benchmark-child-override-' || number)::uuid,
    '2026-01-01 07:30:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 07:30:00+00'::timestamptz
        + number * interval '1 millisecond'
FROM generate_series(5002, 6000, 2) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO product_attribute_values (
    product_id,
    attribute_definition_id,
    value_key,
    position,
    raw_value,
    canonical_value,
    display_value,
    text_value,
    source_type,
    confidence_score,
    validation_status,
    approval_status,
    is_active,
    version,
    id,
    created_at,
    updated_at,
    is_locked
)
SELECT
    md5('benchmark-product-1')::uuid,
    md5('benchmark-attribute-' || number)::uuid,
    'single',
    0,
    to_jsonb('value-' || number),
    to_jsonb('value-' || number),
    'value-' || number,
    'value-' || number,
    'MANUAL',
    1.0,
    'VALID',
    'APPROVED',
    TRUE,
    1,
    md5('benchmark-value-' || number)::uuid,
    '2026-01-01 08:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    '2026-01-01 08:00:00+00'::timestamptz
        + number * interval '1 millisecond',
    FALSE
FROM generate_series(1, 2500) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_families (
    name, slug, description, sort_order, is_active, version, created_at, updated_at, id
)
VALUES (
    'Benchmark Family',
    'benchmark-family',
    'Disposable final-validation family',
    0,
    TRUE,
    1,
    '2026-01-01 09:00:00+00',
    '2026-01-01 09:00:00+00',
    md5('benchmark-family')::uuid
)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_family_items (
    family_id,
    attribute_definition_id,
    sort_order,
    is_active,
    created_at,
    updated_at,
    id
)
SELECT
    md5('benchmark-family')::uuid,
    md5('benchmark-attribute-' || number)::uuid,
    number,
    TRUE,
    '2026-01-01 09:00:00+00',
    '2026-01-01 09:00:00+00',
    md5('benchmark-family-item-' || number)::uuid
FROM generate_series(1, 1000) AS series(number)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_templates (
    name,
    slug,
    description,
    parent_template_id,
    is_active,
    version,
    created_at,
    updated_at,
    id
)
VALUES (
    'Benchmark Template',
    'benchmark-template',
    'Disposable final-validation template',
    NULL,
    TRUE,
    1,
    '2026-01-01 10:00:00+00',
    '2026-01-01 10:00:00+00',
    md5('benchmark-template')::uuid
)
ON CONFLICT DO NOTHING;

INSERT INTO attribute_template_items (
    template_id,
    attribute_definition_id,
    family_id,
    sort_order,
    is_active,
    created_at,
    updated_at,
    id
)
SELECT
    md5('benchmark-template')::uuid,
    md5('benchmark-attribute-' || number)::uuid,
    CASE
        WHEN number <= 1000 THEN md5('benchmark-family')::uuid
        ELSE NULL
    END,
    number,
    TRUE,
    '2026-01-01 10:00:00+00',
    '2026-01-01 10:00:00+00',
    md5('benchmark-template-item-' || number)::uuid
FROM generate_series(1, 2000) AS series(number)
ON CONFLICT DO NOTHING;

ANALYZE;
