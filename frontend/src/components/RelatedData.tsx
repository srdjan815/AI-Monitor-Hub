import { useQueries } from "@tanstack/react-query";
import { Divider, Paper, Stack, Typography } from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { EmptyState, ErrorBlock, LoadingBlock } from "./AsyncState";
import { RecordDetails } from "./RecordDetails";

interface Endpoint {
  label: string;
  path: string;
  collection: boolean;
}

export function RelatedData({
  resource,
  root,
  id
}: {
  resource: string;
  root: string;
  id: string;
}) {
  const endpoints: Endpoint[] =
    resource === "mapping-profiles"
      ? [{ label: "Mapping Rules", path: `${root}/${id}/rules`, collection: true }]
      : resource === "schema-profiles"
      ? [{ label: "Schema Fields", path: `${root}/${id}/fields`, collection: true }]
      : resource === "acquisitions"
        ? [
            { label: "Staged Records", path: `${root}/${id}/records`, collection: true },
            { label: "Row Errors", path: `${root}/${id}/issues`, collection: true },
            { label: "Statistika", path: `${root}/${id}/statistics`, collection: false }
          ]
        : resource === "snapshots"
          ? [
              { label: "Snapshot Items", path: `${root}/${id}/items`, collection: true },
              { label: "Statistika", path: `${root}/${id}/statistics`, collection: false }
            ]
          : resource === "deltas"
            ? [
                { label: "Delta Items", path: `${root}/${id}/items`, collection: true },
                { label: "Sažetak", path: `${root}/${id}/summary`, collection: false }
              ]
            : [];
  const queries = useQueries({
    queries: endpoints.map((endpoint) => ({
      queryKey: ["related", endpoint.path],
      queryFn: () =>
        endpoint.collection
          ? supplierApi.nestedCollection<Record<string, unknown>>(
              endpoint.path,
              { limit: 25, offset: 0 }
            )
          : supplierApi.detail<Record<string, unknown>>(endpoint.path),
      staleTime: 20_000
    }))
  });
  if (!endpoints.length) return null;
  return (
    <Stack gap={2.5} mt={3}>
      <Divider />
      {endpoints.map((endpoint, index) => {
        const query = queries[index];
        const data = query.data as
          | { items?: Array<Record<string, unknown>>; total?: number }
          | Record<string, unknown>
          | undefined;
        const rows = "items" in (data ?? {}) ? (data as any).items : undefined;
        return (
          <Stack key={endpoint.path} gap={1}>
            <Typography variant="h2">{endpoint.label}</Typography>
            {query.isLoading ? (
              <LoadingBlock rows={3} />
            ) : query.isError ? (
              <ErrorBlock error={query.error} retry={() => query.refetch()} />
            ) : rows ? (
              rows.length ? (
                rows.slice(0, 10).map((row: Record<string, unknown>, rowIndex: number) => (
                  <Paper key={String(row.id ?? rowIndex)} variant="outlined" sx={{ p: 1.5 }}>
                    <RecordDetails
                      record={row}
                      exclude={["raw_data", "mapped_data", "change_summary"]}
                    />
                  </Paper>
                ))
              ) : (
                <EmptyState title={`Nema: ${endpoint.label}`} description="Backend nije vratio povezane zapise." />
              )
            ) : data ? (
              <RecordDetails record={data as Record<string, unknown>} />
            ) : null}
          </Stack>
        );
      })}
    </Stack>
  );
}
