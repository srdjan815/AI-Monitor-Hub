export interface PageAccess {
  path: string;
  permission: string;
}

export const PAGE_ACCESS = [
  { path: "/dashboard", permission: "supplier_platform.overview" },
  { path: "/suppliers", permission: "suppliers.read" },
  { path: "/sources", permission: "supplier_sources.read" },
  { path: "/automation", permission: "acquisitions.read" },
  { path: "/schemas", permission: "schema_profiles.read" },
  { path: "/mappings", permission: "mapping_profiles.read" },
  { path: "/acquisitions", permission: "acquisitions.read" },
  { path: "/snapshots", permission: "snapshots.read" },
  { path: "/deltas", permission: "deltas.read" },
  { path: "/incidents", permission: "incidents.read" },
  { path: "/article-reviews", permission: "article_reviews.read" },
  { path: "/supplier-currencies", permission: "currency_rates.read" },
  { path: "/archive", permission: "snapshots.read" },
  { path: "/administration", permission: "incident_rules.read" }
] as const satisfies readonly PageAccess[];

export type PagePath = (typeof PAGE_ACCESS)[number]["path"];

export function canAccess(
  permissions: readonly string[],
  permission: string
): boolean {
  return permissions.includes("*") || permissions.includes(permission);
}

export function firstAccessiblePath(permissions: readonly string[]): PagePath | null {
  return PAGE_ACCESS.find((page) => canAccess(permissions, page.permission))?.path ?? null;
}
