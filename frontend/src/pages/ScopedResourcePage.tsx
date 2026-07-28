import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CancelRounded,
  PlayArrowRounded,
  RefreshRounded,
  UploadFileRounded
} from "@mui/icons-material";
import {
  Button,
  Stack,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { RecordDetails } from "../components/RecordDetails";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { RelatedData } from "../components/RelatedData";
import { useAuth } from "../state/AuthContext";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Operation } from "../types";

export interface ResourceConfiguration {
  resource: string;
  title: string;
  description: string;
  codeField: string;
  permissionRead: string;
  permissionWrite?: string;
  statusField?: string;
  extraColumns?: Array<{
    key: string;
    label: string;
    tooltip: string;
  }>;
  actions?: Array<{
    name: string;
    label: string;
    tooltip: string;
    permission: string;
    icon: "play" | "upload" | "cancel" | "retry";
    body?: Record<string, unknown>;
  }>;
}

const icons = {
  play: <PlayArrowRounded />,
  upload: <UploadFileRounded />,
  cancel: <CancelRounded />,
  retry: <RefreshRounded />
};

export function ScopedResourcePage({ config }: { config: ResourceConfiguration }) {
  const workspace = useWorkspace();
  const auth = useAuth();
  const client = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Operation | null>(null);
  const [filter, setFilter] = useState("");
  const root = `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}/${config.resource}`;
  const result = useQuery({
    queryKey: [config.resource, workspace.supplierId, workspace.sourceId, page, filter],
    queryFn: () =>
      supplierApi.collection<Operation>(
        workspace.supplierId,
        workspace.sourceId,
        config.resource,
        {
          limit: 25,
          offset: page * 25,
          status: filter || undefined
        }
      ),
    enabled:
      Boolean(workspace.supplierId && workspace.sourceId) &&
      auth.can(config.permissionRead),
    placeholderData: (previous) => previous
  });
  const action = useMutation({
    mutationFn: ({ row, name, body }: { row: Operation; name: string; body?: Record<string, unknown> }) =>
      supplierApi.mutate(`${root}/${row.id}/${name}`, "POST", body),
    onSuccess: () => {
      toast.success("Operacija je prihvaćena.");
      client.invalidateQueries({ queryKey: [config.resource] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const execute = useMutation({
    mutationFn: (file?: File) =>
      file
        ? supplierApi.mutate(
            `${root}/upload?filename=${encodeURIComponent(file.name)}`,
            "POST",
            file
          )
        : supplierApi.mutate(`${root}/execute`, "POST", {
            idempotency_key: crypto.randomUUID()
          }),
    onSuccess: () => {
      toast.success("Acquisition je izvršen.");
      client.invalidateQueries({ queryKey: [config.resource] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const createResource = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      supplierApi.mutate(root, "POST", body),
    onSuccess: () => {
      toast.success("Resurs je kreiran.");
      client.invalidateQueries({ queryKey: [config.resource] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const requestCreate = () => {
    if (config.resource === "schema-profiles") {
      const name = prompt("Naziv Schema Profile verzije");
      if (name) createResource.mutate({ name });
    } else if (config.resource === "snapshots") {
      const acquisition_run_id = prompt("Acquisition Run ID");
      if (acquisition_run_id) {
        createResource.mutate({ acquisition_run_id, retention_class: "STANDARD" });
      }
    } else if (config.resource === "deltas") {
      const previous_snapshot_id = prompt("Prethodni Snapshot ID");
      const current_snapshot_id = prompt("Trenutni Snapshot ID");
      if (previous_snapshot_id && current_snapshot_id) {
        createResource.mutate({
          previous_snapshot_id,
          current_snapshot_id,
          idempotency_key: crypto.randomUUID()
        });
      }
    }
  };
  const columns = useMemo<Column<Operation>[]>(
    () => [
      {
        key: config.codeField,
        label: "Šifra",
        tooltip: "Stabilna interna šifra resursa.",
        render: (row) => (
          <Typography fontFamily="monospace">
            {String(row[config.codeField] ?? row.id)}
          </Typography>
        ),
        csv: (row) => String(row[config.codeField] ?? row.id)
      },
      {
        key: "status",
        label: "Status",
        tooltip: "Status koji izračunava i čuva backend.",
        render: (row) => <StatusChip value={String(row[config.statusField ?? "status"] ?? "")} />,
        csv: (row) => String(row[config.statusField ?? "status"] ?? "")
      },
      ...(config.extraColumns ?? []).map<Column<Operation>>((column) => ({
        ...column,
        render: (row) => {
          const value = row[column.key];
          return typeof value === "string" && value.includes("T")
            ? new Date(value).toLocaleString("sr-RS")
            : String(value ?? "—");
        },
        csv: (row) => String(row[column.key] ?? "")
      })),
      {
        key: "created_at",
        label: "Kreirano",
        tooltip: "Vreme kreiranja zapisa.",
        render: (row) => new Date(row.created_at).toLocaleString("sr-RS"),
        csv: (row) => row.created_at
      }
    ],
    [config]
  );
  return (
    <>
      <PageHeader title={config.title} description={config.description} />
      <WorkspaceSelector />
      {["schema-profiles", "snapshots", "deltas"].includes(config.resource) &&
        config.permissionWrite &&
        auth.can(config.permissionWrite) && (
          <Tooltip title="Otvara minimalni unos identifikatora; sva poslovna validacija ostaje na backend-u.">
            <Button
              variant="contained"
              startIcon={<PlayArrowRounded />}
              onClick={requestCreate}
              disabled={!workspace.sourceId || createResource.isPending}
              sx={{ mb: 2 }}
            >
              {config.resource === "schema-profiles"
                ? "Novi Schema Profile"
                : config.resource === "snapshots"
                  ? "Kreiraj Snapshot"
                  : "Izračunaj Delta"}
            </Button>
          </Tooltip>
        )}
      {config.resource === "acquisitions" && (
        <Stack direction={{ xs: "column", sm: "row" }} gap={1} mb={2}>
          <Tooltip title="Pokreće sinhroni Acquisition preko postojeće Source Connection konfiguracije.">
            <span>
              <Button
                variant="contained"
                startIcon={<PlayArrowRounded />}
                disabled={!workspace.sourceId || !auth.can("acquisitions.execute") || execute.isPending}
                onClick={() => execute.mutate(undefined)}
              >
                Manual Execute
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="Šalje izabrani fajl postojećem backend upload endpoint-u; UI ga ne parsira.">
            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadFileRounded />}
              disabled={!workspace.sourceId || !auth.can("acquisitions.upload") || execute.isPending}
            >
              Upload fajla
              <input
                hidden
                type="file"
                accept=".csv,.xml,.xlsx,.xls,text/csv,application/xml"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) execute.mutate(file);
                  event.target.value = "";
                }}
              />
            </Button>
          </Tooltip>
        </Stack>
      )}
      <TextField
        size="small"
        label="Status filter"
        value={filter}
        onChange={(event) => {
          setFilter(event.target.value.toUpperCase());
          setPage(0);
        }}
        helperText="Backend validira dozvoljene status vrednosti."
        sx={{ mb: 2, width: { xs: "100%", sm: 280 } }}
      />
      <EntityTable
        tableId={config.resource}
        columns={columns}
        rows={result.data?.items ?? []}
        total={result.data?.total ?? 0}
        page={page}
        pageSize={25}
        loading={result.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={setOpened}
        onRefresh={() => result.refetch()}
      />
      <DetailDrawer
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={String(opened?.[config.codeField] ?? config.title)}
        subtitle={opened?.id}
        actions={
          opened && config.actions ? (
            <Stack direction="row" gap={1} flexWrap="wrap">
              {config.actions
                .filter((item) => auth.can(item.permission))
                .map((item) => (
                  <Tooltip key={item.name} title={item.tooltip}>
                    <Button
                      startIcon={icons[item.icon]}
                      onClick={() =>
                        action.mutate({ row: opened, name: item.name, body: item.body })
                      }
                    >
                      {item.label}
                    </Button>
                  </Tooltip>
                ))}
            </Stack>
          ) : undefined
        }
      >
        {opened && (
          <>
            <RecordDetails
              record={opened}
              exclude={["raw_data", "mapped_data", "sanitized_context"]}
            />
            <RelatedData resource={config.resource} root={root} id={opened.id} />
          </>
        )}
      </DetailDrawer>
    </>
  );
}

export const resourceConfigurations: Record<string, ResourceConfiguration> = {
  schemas: {
    resource: "schema-profiles",
    title: "Schema Profiles",
    description: "Verzije očekivane strukture, aktivacija, polja i validacija.",
    codeField: "schema_code",
    permissionRead: "schema_profiles.read",
    permissionWrite: "schema_profiles.write",
    extraColumns: [
      { key: "version", label: "Verzija", tooltip: "Nepromjenljiva verzija schema profila." },
      { key: "is_active", label: "Aktivan", tooltip: "Da li profil učestvuje u validaciji." }
    ],
    actions: [
      { name: "activate", label: "Aktiviraj", tooltip: "Aktivira ovu verziju kroz backend lifecycle.", permission: "schema_profiles.activate", icon: "play" },
      { name: "archive", label: "Arhiviraj", tooltip: "Arhivira profil bez brisanja istorije.", permission: "schema_profiles.activate", icon: "cancel" }
    ]
  },
  acquisitions: {
    resource: "acquisitions",
    title: "Acquisition Runs",
    description: "Ručno izvršavanje, upload, retry/cancel, greške, statistika i timeline.",
    codeField: "acquisition_code",
    permissionRead: "acquisitions.read",
    extraColumns: [
      { key: "trigger_type", label: "Trigger", tooltip: "Način pokretanja Acquisition Run-a." },
      { key: "total_record_count", label: "Zapisi", tooltip: "Ukupan broj pročitanih source redova." }
    ],
    actions: [
      { name: "retry", label: "Ponovi", tooltip: "Kreira novi pokušaj preko postojećeg backend servisa.", permission: "acquisitions.execute", icon: "retry" },
      { name: "cancel", label: "Otkaži", tooltip: "Otkazuje dozvoljeni aktivni Run.", permission: "acquisitions.cancel", icon: "cancel" }
    ]
  },
  snapshots: {
    resource: "snapshots",
    title: "Snapshots",
    description: "Validno stanje dobavljača, integritet, items, arhiva i restore.",
    codeField: "snapshot_code",
    permissionRead: "snapshots.read",
    permissionWrite: "snapshots.create",
    statusField: "storage_state",
    extraColumns: [
      { key: "status", label: "Build status", tooltip: "Rezultat izgradnje Snapshot-a." },
      { key: "total_items", label: "Stavke", tooltip: "Broj Snapshot Item zapisa." }
    ],
    actions: [
      { name: "verify", label: "Proveri integritet", tooltip: "Backend ponovo proverava checksum i integritet.", permission: "snapshots.verify", icon: "play" },
      { name: "restore", label: "Vrati online", tooltip: "Pokreće postojeći restore ugovor za arhivirani Snapshot.", permission: "snapshots.restore", icon: "retry" }
    ]
  },
  deltas: {
    resource: "deltas",
    title: "Delta Runs",
    description: "Poređenja Snapshot parova, sažetak i promene po poljima.",
    codeField: "delta_code",
    permissionRead: "deltas.read",
    permissionWrite: "deltas.calculate",
    extraColumns: [
      { key: "added_items", label: "Dodato", tooltip: "Broj dodatih stavki." },
      { key: "modified_items", label: "Izmenjeno", tooltip: "Broj izmenjenih stavki." },
      { key: "removed_items", label: "Uklonjeno", tooltip: "Broj uklonjenih stavki." }
    ],
    actions: [
      { name: "retry", label: "Ponovi", tooltip: "Ponavlja neuspešno poređenje bez promene snapshot-a.", permission: "deltas.calculate", icon: "retry" },
      { name: "cancel", label: "Otkaži", tooltip: "Otkazuje aktivni Delta Run.", permission: "deltas.cancel", icon: "cancel" }
    ]
  }
};
