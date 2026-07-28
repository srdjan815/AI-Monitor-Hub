import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Stack, TextField, Typography } from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { RecordDetails } from "../components/RecordDetails";
import { RelatedData } from "../components/RelatedData";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useWorkspace } from "../state/WorkspaceContext";
import { useAuth } from "../state/AuthContext";
import toast from "react-hot-toast";
import type { ApiError, Operation } from "../types";

export function MappingProfilesPage() {
  const workspace = useWorkspace();
  const auth = useAuth();
  const client = useQueryClient();
  const [schemaId, setSchemaId] = useState(localStorage.getItem("amh.schema-id") ?? "");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Operation | null>(null);
  const root = `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}/schema-profiles/${schemaId}/mapping-profiles`;
  const mappings = useQuery({
    queryKey: ["mapping-profiles", workspace.supplierId, workspace.sourceId, schemaId, page],
    queryFn: () => supplierApi.nestedCollection<Operation>(root, { limit: 25, offset: page * 25 }),
    enabled: Boolean(workspace.supplierId && workspace.sourceId && schemaId)
  });
  const create = useMutation({
    mutationFn: (name: string) =>
      supplierApi.mutate(root, "POST", { name }),
    onSuccess: () => {
      toast.success("Mapping Profile je kreiran.");
      client.invalidateQueries({ queryKey: ["mapping-profiles"] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const columns = useMemo<Column<Operation>[]>(
    () => [
      {
        key: "mapping_code",
        label: "Šifra",
        tooltip: "Stabilna šifra Mapping Profile verzije.",
        render: (row) => <Typography fontFamily="monospace">{String(row.mapping_code ?? row.id)}</Typography>,
        csv: (row) => String(row.mapping_code ?? row.id)
      },
      {
        key: "name",
        label: "Naziv",
        tooltip: "Administrativni naziv mapping konfiguracije.",
        render: (row) => <Typography fontWeight={650}>{String(row.name ?? "—")}</Typography>,
        csv: (row) => String(row.name ?? "")
      },
      {
        key: "status",
        label: "Status",
        tooltip: "Lifecycle status profila.",
        render: (row) => <StatusChip value={String(row.status ?? "")} />,
        csv: (row) => String(row.status ?? "")
      },
      {
        key: "version",
        label: "Verzija",
        tooltip: "Verzija koju backend koristi za reproducibilan import.",
        render: (row) => String(row.version ?? "—"),
        csv: (row) => String(row.version ?? "")
      }
    ],
    []
  );
  return (
    <>
      <PageHeader
        title="Mapping Profiles"
        description="Rule editor, transformacije, validacija, aktivacija i istorija verzija."
      />
      <WorkspaceSelector />
      <Stack direction={{ xs: "column", sm: "row" }} gap={1} mb={2}>
        <TextField
          size="small"
          label="Schema Profile ID"
          value={schemaId}
          onChange={(event) => {
            setSchemaId(event.target.value);
            localStorage.setItem("amh.schema-id", event.target.value);
          }}
          helperText="Mapping pripada konkretnoj schema verziji; ID dolazi iz Schema Profiles ekrana."
          sx={{ width: { xs: "100%", sm: 440 } }}
        />
        <Button
          variant="outlined"
          onClick={() => mappings.refetch()}
          disabled={!schemaId}
        >
          Učitaj profile
        </Button>
        {auth.can("mapping_profiles.write") && (
          <Button
            variant="contained"
            disabled={!schemaId || create.isPending}
            onClick={() => {
              const name = prompt("Naziv Mapping Profile verzije");
              if (name) create.mutate(name);
            }}
          >
            Novi Mapping Profile
          </Button>
        )}
      </Stack>
      <EntityTable
        tableId="mapping-profiles"
        columns={columns}
        rows={mappings.data?.items ?? []}
        total={mappings.data?.total ?? 0}
        page={page}
        pageSize={25}
        loading={mappings.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={setOpened}
        onRefresh={() => mappings.refetch()}
      />
      <DetailDrawer
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={String(opened?.mapping_code ?? "Mapping Profile")}
        subtitle="Pravila se učitavaju tek po otvaranju detalja."
      >
        {opened && (
          <>
            <RecordDetails record={opened} />
            <RelatedData resource="mapping-profiles" root={root} id={opened.id} />
          </>
        )}
      </DetailDrawer>
    </>
  );
}
