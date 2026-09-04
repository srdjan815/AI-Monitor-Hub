from __future__ import annotations

from typing import Final

CATALOG_READ = "catalog.read"
CATALOG_WRITE = "catalog.write"
CATALOG_SEED = "catalog.seed"
ATTRIBUTES_READ = "attributes.read"
ATTRIBUTES_WRITE = "attributes.write"
ATTRIBUTES_APPROVE = "attributes.approve"
CONTENT_READ = "content.read"
CONTENT_WRITE = "content.write"
CONTENT_APPROVE = "content.approve"
CONTENT_RAW_PREVIEW = "content.raw_preview"
CONTENT_PROMPT_MANAGE = "content.prompt_manage"
CONTENT_SCORING_MANAGE = "content.scoring_manage"
INVENTORY_READ = "inventory.read"
INVENTORY_WRITE = "inventory.write"
INVENTORY_ADJUST = "inventory.adjust"
EXECUTION_READ = "execution.read"
EXECUTION_SUBMIT = "execution.submit"
EXECUTION_MANAGE = "execution.manage"
SUPPLIERS_READ = "suppliers.read"
SUPPLIERS_WRITE = "suppliers.write"
SUPPLIER_SOURCES_READ = "supplier_sources.read"
SUPPLIER_SOURCES_WRITE = "supplier_sources.write"
SUPPLIER_SOURCES_VALIDATE = "supplier_sources.validate"
SCHEMA_PROFILES_READ = "schema_profiles.read"
SCHEMA_PROFILES_WRITE = "schema_profiles.write"
SCHEMA_PROFILES_ACTIVATE = "schema_profiles.activate"
MAPPING_PROFILES_READ = "mapping_profiles.read"
MAPPING_PROFILES_WRITE = "mapping_profiles.write"
MAPPING_PROFILES_ACTIVATE = "mapping_profiles.activate"
ACQUISITIONS_READ = "acquisitions.read"
ACQUISITIONS_EXECUTE = "acquisitions.execute"
ACQUISITIONS_UPLOAD = "acquisitions.upload"
ACQUISITIONS_CANCEL = "acquisitions.cancel"
SNAPSHOTS_READ = "snapshots.read"
SNAPSHOTS_CREATE = "snapshots.create"
SNAPSHOTS_VERIFY = "snapshots.verify"
SNAPSHOTS_ARCHIVE = "snapshots.archive"
SNAPSHOTS_OFFLOAD = "snapshots.offload"
SNAPSHOTS_RESTORE = "snapshots.restore"
DELTAS_READ = "deltas.read"
DELTAS_CALCULATE = "deltas.calculate"
DELTAS_CANCEL = "deltas.cancel"
INCIDENTS_READ = "incidents.read"
INCIDENTS_CREATE = "incidents.create"
INCIDENTS_ACKNOWLEDGE = "incidents.acknowledge"
INCIDENTS_ASSIGN = "incidents.assign"
INCIDENTS_MANAGE = "incidents.manage"
INCIDENTS_RESOLVE = "incidents.resolve"
INCIDENTS_DISMISS = "incidents.dismiss"
INCIDENTS_SUPPRESS = "incidents.suppress"
INCIDENTS_COMMENT = "incidents.comment"
INCIDENT_RULES_READ = "incident_rules.read"
INCIDENT_RULES_MANAGE = "incident_rules.manage"
SUPPLIER_PLATFORM_OVERVIEW = "supplier_platform.overview"
SUPPLIER_PLATFORM_SEARCH = "supplier_platform.search"
ARTICLE_REVIEWS_READ = "article_reviews.read"
ARTICLE_REVIEWS_DECIDE = "article_reviews.decide"
CURRENCY_RATES_READ = "currency_rates.read"
CURRENCY_RATES_WRITE = "currency_rates.write"
ADMIN_ACCESS = "admin.access"

ALL_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        CATALOG_READ,
        CATALOG_WRITE,
        CATALOG_SEED,
        ATTRIBUTES_READ,
        ATTRIBUTES_WRITE,
        ATTRIBUTES_APPROVE,
        CONTENT_READ,
        CONTENT_WRITE,
        CONTENT_APPROVE,
        CONTENT_RAW_PREVIEW,
        CONTENT_PROMPT_MANAGE,
        CONTENT_SCORING_MANAGE,
        INVENTORY_READ,
        INVENTORY_WRITE,
        INVENTORY_ADJUST,
        EXECUTION_READ,
        EXECUTION_SUBMIT,
        EXECUTION_MANAGE,
        SUPPLIERS_READ,
        SUPPLIERS_WRITE,
        SUPPLIER_SOURCES_READ,
        SUPPLIER_SOURCES_WRITE,
        SUPPLIER_SOURCES_VALIDATE,
        SCHEMA_PROFILES_READ,
        SCHEMA_PROFILES_WRITE,
        SCHEMA_PROFILES_ACTIVATE,
        MAPPING_PROFILES_READ,
        MAPPING_PROFILES_WRITE,
        MAPPING_PROFILES_ACTIVATE,
        ACQUISITIONS_READ,
        ACQUISITIONS_EXECUTE,
        ACQUISITIONS_UPLOAD,
        ACQUISITIONS_CANCEL,
        SNAPSHOTS_READ,
        SNAPSHOTS_CREATE,
        SNAPSHOTS_VERIFY,
        SNAPSHOTS_ARCHIVE,
        SNAPSHOTS_OFFLOAD,
        SNAPSHOTS_RESTORE,
        DELTAS_READ,
        DELTAS_CALCULATE,
        DELTAS_CANCEL,
        INCIDENTS_READ,
        INCIDENTS_CREATE,
        INCIDENTS_ACKNOWLEDGE,
        INCIDENTS_ASSIGN,
        INCIDENTS_MANAGE,
        INCIDENTS_RESOLVE,
        INCIDENTS_DISMISS,
        INCIDENTS_SUPPRESS,
        INCIDENTS_COMMENT,
        INCIDENT_RULES_READ,
        INCIDENT_RULES_MANAGE,
        SUPPLIER_PLATFORM_OVERVIEW,
        SUPPLIER_PLATFORM_SEARCH,
        ARTICLE_REVIEWS_READ,
        ARTICLE_REVIEWS_DECIDE,
        CURRENCY_RATES_READ,
        CURRENCY_RATES_WRITE,
        ADMIN_ACCESS,
    }
)

ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "system_admin": ALL_PERMISSIONS,
    "catalog_admin": frozenset(
        {
            CATALOG_READ,
            CATALOG_WRITE,
            CATALOG_SEED,
            ATTRIBUTES_READ,
            ATTRIBUTES_WRITE,
            ATTRIBUTES_APPROVE,
        }
    ),
    "content_editor": frozenset(
        {
            CATALOG_READ,
            ATTRIBUTES_READ,
            CONTENT_READ,
            CONTENT_WRITE,
        }
    ),
    "content_approver": frozenset(
        {CATALOG_READ, ATTRIBUTES_READ, CONTENT_READ, CONTENT_WRITE, CONTENT_APPROVE}
    ),
    "inventory_operator": frozenset(
        {CATALOG_READ, INVENTORY_READ, INVENTORY_WRITE, INVENTORY_ADJUST}
    ),
    "execution_operator": frozenset(
        {EXECUTION_READ, EXECUTION_SUBMIT, EXECUTION_MANAGE}
    ),
    "supplier_admin": frozenset(
        {
            SUPPLIERS_READ,
            SUPPLIERS_WRITE,
            SUPPLIER_SOURCES_READ,
            SUPPLIER_SOURCES_WRITE,
            SUPPLIER_SOURCES_VALIDATE,
            SCHEMA_PROFILES_READ,
            SCHEMA_PROFILES_WRITE,
            SCHEMA_PROFILES_ACTIVATE,
            MAPPING_PROFILES_READ,
            MAPPING_PROFILES_WRITE,
            MAPPING_PROFILES_ACTIVATE,
            ACQUISITIONS_READ,
            ACQUISITIONS_EXECUTE,
            ACQUISITIONS_UPLOAD,
            ACQUISITIONS_CANCEL,
            SNAPSHOTS_READ,
            SNAPSHOTS_CREATE,
            SNAPSHOTS_VERIFY,
            SNAPSHOTS_ARCHIVE,
            SNAPSHOTS_OFFLOAD,
            SNAPSHOTS_RESTORE,
            DELTAS_READ,
            DELTAS_CALCULATE,
            DELTAS_CANCEL,
            INCIDENTS_READ,
            INCIDENTS_CREATE,
            INCIDENTS_ACKNOWLEDGE,
            INCIDENTS_ASSIGN,
            INCIDENTS_MANAGE,
            INCIDENTS_RESOLVE,
            INCIDENTS_DISMISS,
            INCIDENTS_SUPPRESS,
            INCIDENTS_COMMENT,
            INCIDENT_RULES_READ,
            INCIDENT_RULES_MANAGE,
            SUPPLIER_PLATFORM_OVERVIEW,
            SUPPLIER_PLATFORM_SEARCH,
            ARTICLE_REVIEWS_READ,
            ARTICLE_REVIEWS_DECIDE,
            CURRENCY_RATES_READ,
            CURRENCY_RATES_WRITE,
        }
    ),
    "supplier_source_validator": frozenset(
        {SUPPLIER_SOURCES_READ, SUPPLIER_SOURCES_VALIDATE}
    ),
    "schema_profile_editor": frozenset(
        {SUPPLIER_SOURCES_READ, SCHEMA_PROFILES_READ, SCHEMA_PROFILES_WRITE}
    ),
    "schema_profile_activator": frozenset(
        {SUPPLIER_SOURCES_READ, SCHEMA_PROFILES_READ, SCHEMA_PROFILES_ACTIVATE}
    ),
    "mapping_profile_editor": frozenset(
        {
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            MAPPING_PROFILES_WRITE,
        }
    ),
    "mapping_profile_activator": frozenset(
        {
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            MAPPING_PROFILES_ACTIVATE,
        }
    ),
    "acquisition_operator": frozenset(
        {
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            ACQUISITIONS_READ,
            ACQUISITIONS_EXECUTE,
            ACQUISITIONS_UPLOAD,
            ACQUISITIONS_CANCEL,
        }
    ),
    "snapshot_operator": frozenset(
        {
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            ACQUISITIONS_READ,
            SNAPSHOTS_READ,
            SNAPSHOTS_CREATE,
            SNAPSHOTS_VERIFY,
            SNAPSHOTS_ARCHIVE,
            SNAPSHOTS_RESTORE,
            DELTAS_READ,
            DELTAS_CALCULATE,
            DELTAS_CANCEL,
            INCIDENTS_READ,
            INCIDENTS_CREATE,
            INCIDENTS_ACKNOWLEDGE,
            INCIDENTS_ASSIGN,
            INCIDENTS_MANAGE,
            INCIDENTS_RESOLVE,
            INCIDENTS_DISMISS,
            INCIDENTS_SUPPRESS,
            INCIDENTS_COMMENT,
            INCIDENT_RULES_READ,
            SUPPLIER_PLATFORM_OVERVIEW,
            SUPPLIER_PLATFORM_SEARCH,
            ARTICLE_REVIEWS_READ,
            ARTICLE_REVIEWS_DECIDE,
            CURRENCY_RATES_READ,
            CURRENCY_RATES_WRITE,
        }
    ),
    "read_only": frozenset(
        {
            CATALOG_READ,
            ATTRIBUTES_READ,
            CONTENT_READ,
            INVENTORY_READ,
            EXECUTION_READ,
            SUPPLIERS_READ,
            SUPPLIER_SOURCES_READ,
            SCHEMA_PROFILES_READ,
            MAPPING_PROFILES_READ,
            ACQUISITIONS_READ,
            SNAPSHOTS_READ,
            DELTAS_READ,
            INCIDENTS_READ,
            INCIDENT_RULES_READ,
            SUPPLIER_PLATFORM_OVERVIEW,
            SUPPLIER_PLATFORM_SEARCH,
            ARTICLE_REVIEWS_READ,
            CURRENCY_RATES_READ,
        }
    ),
    "internal_service": ALL_PERMISSIONS,
}
