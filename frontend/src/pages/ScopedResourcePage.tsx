import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CancelRounded,
  PlayArrowRounded,
  RefreshRounded,
  SearchRounded,
  UploadFileRounded
} from "@mui/icons-material";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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

interface SchemaAnalysis {
  profile: Operation;
  original_filename?: string | null;
  detected_format: string;
  encoding?: string | null;
  delimiter?: string | null;
  header_row?: number | null;
  record_count: number;
  sampled_record_count: number;
  fields: Array<{
    field: {
      id: string;
      position: number;
      name: string;
      data_type: string;
      nullable: boolean;
    };
    sample_values: string[];
    confidence: number;
  }>;
}

interface PriceListRecord {
  manufacturer_code?: string | null;
  ean?: string | null;
  name?: string | null;
  price?: string | null;
  duplicate_count: number;
  values: Record<string, string | null>;
}

interface PriceListRecordPage {
  items: PriceListRecord[];
  total: number;
  source_record_count: number;
}

function isSchemaAnalysis(value: unknown): value is SchemaAnalysis {
  return Boolean(
    value &&
      typeof value === "object" &&
      "profile" in value &&
      "fields" in value &&
      Array.isArray((value as SchemaAnalysis).fields)
  );
}

function readableSupplierValue(value: string | null): string {
  if (!value) return "—";
  if (!/<[a-z][\s\S]*>/i.test(value)) return value;
  const document = new DOMParser().parseFromString(value, "text/html");
  const rows = [...document.querySelectorAll("tr")]
    .map((row) => {
      const label = row.querySelector("th")?.textContent?.trim();
      const content = row.querySelector("td")?.textContent?.trim();
      return label && content ? `${label}: ${content}` : null;
    })
    .filter((row): row is string => Boolean(row));
  if (rows.length) return rows.join("\n");
  return (document.body.textContent ?? "")
    .replace(/\s+/g, " ")
    .trim() || "—";
}

export function ScopedResourcePage({ config }: { config: ResourceConfiguration }) {
  const workspace = useWorkspace();
  const auth = useAuth();
  const client = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Operation | null>(null);
  const [analysis, setAnalysis] = useState<SchemaAnalysis | null>(() => {
    if (!window.location.search.includes("analysis=1")) return null;
    try {
      const stored = localStorage.getItem("amh.schema-analysis");
      const value: unknown = stored ? JSON.parse(stored) : null;
      return isSchemaAnalysis(value) ? value : null;
    } catch {
      return null;
    }
  });
  const [filter, setFilter] = useState("");
  const [selectedSchemaId, setSelectedSchemaId] = useState("");
  const [recordSearch, setRecordSearch] = useState("");
  const [appliedRecordSearch, setAppliedRecordSearch] = useState("");
  const [recordPage, setRecordPage] = useState(0);
  const [openedRecord, setOpenedRecord] = useState<PriceListRecord | null>(null);
  const [selectedAcquisitionId, setSelectedAcquisitionId] = useState("");
  const schemaDebug =
    config.resource === "schema-profiles" &&
    new URLSearchParams(window.location.search).get("debug") === "1";
  const root = `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}/${config.resource}`;
  const result = useQuery({
    queryKey: [config.resource, workspace.supplierId, workspace.sourceId, page, filter],
    queryFn: () =>
      supplierApi.collection<Operation>(
        workspace.supplierId,
        workspace.sourceId,
        config.resource,
        {
          limit: config.resource === "schema-profiles" ? 100 : 25,
          offset: config.resource === "schema-profiles" ? 0 : page * 25,
          active_only:
            config.resource === "schema-profiles" ? false : undefined,
          status: filter || undefined
        }
      ),
    enabled: Boolean(workspace.supplierId && workspace.sourceId),
    placeholderData: (previous) => previous
  });
  useEffect(() => {
    if (
      config.resource === "schema-profiles" &&
      !selectedSchemaId &&
      result.data?.items.length
    ) {
      setSelectedSchemaId(result.data.items[0].id);
    }
  }, [config.resource, result.data?.items, selectedSchemaId]);
  const selectedSchema =
    config.resource === "schema-profiles"
      ? result.data?.items.find((item) => item.id === selectedSchemaId) ?? null
      : null;
  const schemaFields = useQuery({
    queryKey: ["schema-analysis-fields", selectedSchemaId],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `${root}/${selectedSchemaId}/fields`,
        { limit: 500, offset: 0, active_only: true }
      ),
    enabled:
      config.resource === "schema-profiles" &&
      Boolean(workspace.sourceId && selectedSchemaId)
  });
  const acquisitionSchemas = useQuery({
    queryKey: [
      "acquisition-readiness-schemas",
      workspace.supplierId,
      workspace.sourceId
    ],
    queryFn: () =>
      supplierApi.collection<Operation>(
        workspace.supplierId,
        workspace.sourceId,
        "schema-profiles",
        { active_only: true, status: "ACTIVE", limit: 1, offset: 0 }
      ),
    enabled:
      config.resource === "acquisitions" &&
      Boolean(workspace.supplierId && workspace.sourceId)
  });
  const activeAcquisitionSchema = acquisitionSchemas.data?.items[0] ?? null;
  const acquisitionMappings = useQuery({
    queryKey: [
      "acquisition-readiness-mappings",
      workspace.sourceId,
      activeAcquisitionSchema?.id
    ],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}/schema-profiles/${activeAcquisitionSchema?.id}/mapping-profiles`,
        { active_only: true, status: "ACTIVE", limit: 1, offset: 0 }
      ),
    enabled:
      config.resource === "acquisitions" &&
      Boolean(workspace.sourceId && activeAcquisitionSchema?.id)
  });
  const activeAcquisitionMapping =
    acquisitionMappings.data?.items[0] ?? null;
  const snapshotAcquisitions = useQuery({
    queryKey: [
      "snapshot-eligible-acquisitions",
      workspace.supplierId,
      workspace.sourceId
    ],
    queryFn: () =>
      supplierApi.collection<Operation>(
        workspace.supplierId,
        workspace.sourceId,
        "acquisitions",
        { limit: 100, offset: 0 }
      ),
    enabled:
      config.resource === "snapshots" &&
      Boolean(workspace.supplierId && workspace.sourceId),
    refetchOnMount: "always"
  });
  const snapshottedAcquisitions = useMemo(
    () =>
      new Set(
        (config.resource === "snapshots" ? result.data?.items ?? [] : []).map(
          (snapshot) => String(snapshot.acquisition_run_id)
        )
      ),
    [config.resource, result.data?.items]
  );
  const latestAcquisition = snapshotAcquisitions.data?.items[0] ?? null;
  const eligibleAcquisitions = useMemo(
    () =>
      latestAcquisition &&
      ["SUCCEEDED", "PARTIALLY_SUCCEEDED"].includes(
        String(latestAcquisition.status)
      ) &&
      Number(latestAcquisition.accepted_record_count ?? 0) > 0 &&
      !snapshottedAcquisitions.has(latestAcquisition.id)
        ? [latestAcquisition]
        : [],
    [latestAcquisition, snapshottedAcquisitions]
  );
  useEffect(() => {
    if (
      config.resource === "snapshots" &&
      !selectedAcquisitionId &&
      eligibleAcquisitions.length
    ) {
      setSelectedAcquisitionId(eligibleAcquisitions[0].id);
    }
  }, [config.resource, eligibleAcquisitions, selectedAcquisitionId]);
  const selectedAcquisition =
    eligibleAcquisitions.find((run) => run.id === selectedAcquisitionId) ??
    null;
  const priceListRecords = useQuery({
    queryKey: [
      "schema-price-list-records",
      selectedSchemaId,
      appliedRecordSearch,
      recordPage
    ],
    queryFn: () =>
      supplierApi.get<PriceListRecordPage>(
        `${root}/${selectedSchemaId}/records`,
        {
          search: appliedRecordSearch || undefined,
          limit: 25,
          offset: recordPage * 25
        }
      ),
    enabled:
      config.resource === "schema-profiles" &&
      Boolean(workspace.sourceId && selectedSchemaId)
  });
  useEffect(() => {
    setRecordPage(0);
    setAppliedRecordSearch("");
    setRecordSearch("");
  }, [selectedSchemaId]);
  const action = useMutation({
    mutationFn: ({ row, name, body }: { row: Operation; name: string; body?: Record<string, unknown> }) =>
      supplierApi.mutate(
        `${root}/${row.id}/${name}`,
        "POST",
        body ?? { version: row.version }
      ),
    onSuccess: (data) => {
      toast.success("Operacija je prihvaćena.");
      if (isSchemaAnalysis(data)) setAnalysis(data);
      client.invalidateQueries({ queryKey: [config.resource] });
      client.invalidateQueries({ queryKey: ["schema-analysis-fields"] });
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
    onSuccess: (data) => {
      if (String(data.status) === "FAILED") {
        toast.error(
          String(
            data.failure_message ??
              "Import cenovnika nije uspešno završen."
          )
        );
      } else {
        toast.success("Import cenovnika je uspešno završen.");
      }
      client.invalidateQueries({ queryKey: [config.resource] });
      client.invalidateQueries({ queryKey: ["snapshot-eligible-acquisitions"] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const createResource = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      supplierApi.mutate(
        config.resource === "schema-profiles" ? `${root}/analyze` : root,
        "POST",
        body
      ),
    onSuccess: (data) => {
      if (isSchemaAnalysis(data)) {
        setAnalysis(data);
        setSelectedSchemaId(data.profile.id);
        toast.success("Cenovnik je preuzet i analiziran.");
      } else if (config.resource === "snapshots") {
        toast.success(
          `Snapshot ${String(data.snapshot_code ?? "")} je uspešno kreiran.`
        );
      } else {
        toast.success("Resurs je kreiran.");
      }
      client.invalidateQueries({ queryKey: [config.resource] });
      client.invalidateQueries({
        queryKey: ["snapshot-eligible-acquisitions"]
      });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const startMapping = useMutation({
    mutationFn: async (result: SchemaAnalysis) => {
      const mappingRoot =
        `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}` +
        `/schema-profiles/${result.profile.id}/mapping-profiles`;
      const existing = await supplierApi.nestedCollection<Operation>(mappingRoot, {
        active_only: false,
        limit: 100,
        offset: 0
      });
      const draft = existing.items.find((item) => item.status === "DRAFT");
      const mapping =
        draft ??
        (await supplierApi.mutate<Operation>(mappingRoot, "POST", {
          name: `Mapiranje ${result.original_filename ?? result.profile.schema_code ?? "cenovnika"}`
        }));
      return { mapping, result };
    },
    onSuccess: ({ mapping, result }) => {
      localStorage.setItem("amh.schema-id", result.profile.id);
      localStorage.setItem("amh.mapping-id", mapping.id);
      localStorage.setItem("amh.schema-analysis", JSON.stringify(result));
      window.location.assign("/mappings");
    },
    onError: (error: ApiError) => toast.error(error.message)
  });
  const requestCreate = () => {
    if (config.resource === "schema-profiles") {
      createResource.mutate({
        name: `Analiza cenovnika ${new Date().toLocaleString("sr-RS")}`
      });
    } else if (config.resource === "snapshots") {
      if (selectedAcquisitionId) {
        createResource.mutate({
          acquisition_run_id: selectedAcquisitionId,
          retention_class: "STANDARD"
        });
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
          return typeof value === "string" &&
            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value)
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
      {config.resource === "schema-profiles" && (
        <Stack gap={1.5} mb={2}>
          <Alert severity={workspace.sourceId ? "success" : "info"}>
            {workspace.sourceId
              ? "Dobavljač i Source Connection su izabrani. Možete preuzeti cenovnik."
              : "Izaberite dobavljača i Source Connection da biste preuzeli cenovnik."}
          </Alert>
          <Stack direction={{ xs: "column", sm: "row" }} gap={1}>
            <Tooltip
              title={
                !workspace.sourceId
                  ? "Prvo izaberite dobavljača i njegov izvor."
                  : "Preuzima cenovnik, bezbedno ga čuva i pronalazi polja."
              }
            >
              <span>
                <Button
                  variant="contained"
                  startIcon={<PlayArrowRounded />}
                  onClick={requestCreate}
                  disabled={!workspace.sourceId || createResource.isPending}
                >
                  Importuj cenovnik
                </Button>
              </span>
            </Tooltip>
            <Tooltip
              title={
                !selectedSchema
                  ? "Prvo izaberite preuzeti cenovnik iz liste ispod."
                  : "Ponovo analizira izabrani DRAFT cenovnik i osvežava polja."
              }
            >
              <span>
                <Button
                  variant="outlined"
                  startIcon={<RefreshRounded />}
                  disabled={
                    !selectedSchema ||
                    String(selectedSchema.status) !== "DRAFT" ||
                    action.isPending
                  }
                  onClick={() =>
                    selectedSchema &&
                    action.mutate({
                      row: selectedSchema,
                      name: "reanalyze",
                      body: { version: selectedSchema.version }
                    })
                  }
                >
                  Analiziraj cenovnik
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
      )}
      {config.resource === "deltas" &&
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
              Izračunaj Delta
            </Button>
          </Tooltip>
        )}
      {config.resource === "snapshots" && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Stack gap={2}>
            <Typography variant="h6">Kreiraj validno stanje cenovnika</Typography>
            <Typography color="text.secondary">
              Snapshot se uvek kreira iz poslednjeg importa i sadrži samo
              prihvaćene artikle. Stariji cenovnici ostaju istorija i ne mogu
              se slučajno vratiti u aktivni tok.
            </Typography>
            <TextField
              select
              size="small"
              label="Poslednji import"
              value={selectedAcquisitionId}
              onChange={(event) =>
                setSelectedAcquisitionId(event.target.value)
              }
              sx={{ maxWidth: 650 }}
            >
              {snapshotAcquisitions.isLoading && (
                <MenuItem disabled value="">
                  Učitavanje završenih importa…
                </MenuItem>
              )}
              {!snapshotAcquisitions.isLoading &&
                !eligibleAcquisitions.length && (
                  <MenuItem disabled value="">
                    Poslednji import nije spreman ili već ima Snapshot
                  </MenuItem>
                )}
              {eligibleAcquisitions.map((run) => (
                <MenuItem key={run.id} value={run.id}>
                  {String(run.acquisition_code)} · {String(run.status)} ·{" "}
                  {String(run.accepted_record_count ?? 0)} prihvaćeno
                </MenuItem>
              ))}
            </TextField>
            {selectedAcquisition && (
              <Stack direction={{ xs: "column", sm: "row" }} gap={3}>
                <Typography>
                  Ukupno:{" "}
                  <strong>
                    {String(selectedAcquisition.total_record_count ?? 0)}
                  </strong>
                </Typography>
                <Typography color="success.main">
                  Prihvaćeno:{" "}
                  <strong>
                    {String(selectedAcquisition.accepted_record_count ?? 0)}
                  </strong>
                </Typography>
                <Typography color="error.main">
                  Odbijeno:{" "}
                  <strong>
                    {String(selectedAcquisition.rejected_record_count ?? 0)}
                  </strong>
                </Typography>
                <StatusChip value={String(selectedAcquisition.status)} />
              </Stack>
            )}
            <Alert severity={selectedAcquisition ? "info" : "warning"}>
              {selectedAcquisition
                ? `Biće sačuvano ${String(selectedAcquisition.accepted_record_count ?? 0)} validnih artikala. Kreiranje ne menja Catalog.`
                : "Prvo mora postojati uspešan ili delimično uspešan import sa prihvaćenim artiklima."}
            </Alert>
            <Button
              variant="contained"
              startIcon={<PlayArrowRounded />}
              onClick={requestCreate}
              disabled={!selectedAcquisition || createResource.isPending}
              sx={{ alignSelf: "flex-start" }}
            >
              Kreiraj Snapshot
            </Button>
          </Stack>
        </Paper>
      )}
      {config.resource === "acquisitions" && (
        <Stack gap={1.5} mb={2}>
          {workspace.sourceId && !acquisitionSchemas.isLoading && (
            <Alert
              severity={
                activeAcquisitionSchema && activeAcquisitionMapping
                  ? "success"
                  : "warning"
              }
            >
              {!activeAcquisitionSchema
                ? "Import još nije spreman: Schema i Mapping su sačuvani kao DRAFT. Na stranici Mapiranje polja prvo testirajte mapiranje i kliknite „Aktiviraj“."
                : !activeAcquisitionMapping
                  ? "Import još nije spreman: aktivna Schema postoji, ali aktivni Mapping nije pronađen."
                  : "Import je spreman: aktivna Schema i Mapping konfiguracija su pronađene."}
            </Alert>
          )}
          <Stack direction={{ xs: "column", sm: "row" }} gap={1}>
          <Tooltip title="Pokreće sinhroni Acquisition preko postojeće Source Connection konfiguracije.">
            <span>
              <Button
                variant="contained"
                startIcon={<PlayArrowRounded />}
                disabled={!workspace.sourceId || execute.isPending}
                onClick={() => execute.mutate(undefined)}
              >
                Importuj cenovnik
              </Button>
            </span>
          </Tooltip>
          <Tooltip title="Šalje izabrani fajl postojećem backend upload endpoint-u; UI ga ne parsira.">
            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadFileRounded />}
              disabled={!workspace.sourceId || execute.isPending}
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
        </Stack>
      )}
      {config.resource === "schema-profiles" && !schemaDebug && !analysis ? (
        <Stack gap={2}>
          <Typography color="text.secondary">
            Kliknite „Importuj cenovnik“ da sačuvate originalni fajl i
            analizirate njegova polja. Ranije preuzeti cenovnik možete izabrati
            ispod.
          </Typography>
          <TextField
            select
            size="small"
            label="Izaberite preuzeti cenovnik"
            value={selectedSchemaId}
            onChange={(event) => setSelectedSchemaId(event.target.value)}
            sx={{ maxWidth: 520 }}
          >
            {result.isLoading && (
              <MenuItem disabled value="">
                Učitavanje preuzetih cenovnika…
              </MenuItem>
            )}
            {!result.isLoading && !(result.data?.items.length ?? 0) && (
              <MenuItem disabled value="">
                Nema uspešno preuzetih cenovnika za ovaj izvor
              </MenuItem>
            )}
            {(result.data?.items ?? []).map((profile) => (
              <MenuItem key={profile.id} value={profile.id}>
                {String(profile.name)} · {String(profile.status)} ·{" "}
                {String(profile.baseline_record_count ?? 0)} proizvoda
              </MenuItem>
            ))}
          </TextField>
          {selectedSchema && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Stack gap={2}>
                <Stack direction={{ xs: "column", sm: "row" }} gap={3}>
                  <Typography fontWeight={700}>{String(selectedSchema.name)}</Typography>
                  <Typography>
                    Format: {String(selectedSchema.detected_format ?? "—")}
                  </Typography>
                  <Typography>
                    Proizvoda: {String(selectedSchema.baseline_record_count ?? 0)}
                  </Typography>
                  <Typography>
                    Polja: {String(selectedSchema.field_count ?? 0)}
                  </Typography>
                  <StatusChip value={String(selectedSchema.status)} />
                </Stack>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Polje u cenovniku</TableCell>
                        <TableCell>Primer sadržaja</TableCell>
                        <TableCell>Prepoznati tip</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(schemaFields.data?.items ?? []).map((field) => (
                        <TableRow key={field.id}>
                          <TableCell>{String(field.name)}</TableCell>
                          <TableCell>{String(field.example_value ?? "—")}</TableCell>
                          <TableCell>{String(field.data_type)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <Typography variant="h6">Sadržaj cenovnika</Typography>
                <Typography color="text.secondary">
                  Pretražite sve artikle po šifri proizvođača, EAN kodu, nazivu,
                  ceni ili bilo kojoj drugoj vrednosti iz izvornog cenovnika.
                </Typography>
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  gap={1}
                  component="form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    setRecordPage(0);
                    setAppliedRecordSearch(recordSearch.trim());
                  }}
                >
                  <TextField
                    size="small"
                    label="Pretraži artikle"
                    placeholder="Šifra, naziv, EAN ili cena"
                    value={recordSearch}
                    onChange={(event) => setRecordSearch(event.target.value)}
                    sx={{ width: { xs: "100%", sm: 440 } }}
                  />
                  <Button
                    type="submit"
                    variant="outlined"
                    startIcon={<SearchRounded />}
                  >
                    Pretraži
                  </Button>
                  {appliedRecordSearch && (
                    <Button
                      onClick={() => {
                        setRecordSearch("");
                        setAppliedRecordSearch("");
                        setRecordPage(0);
                      }}
                    >
                      Obriši pretragu
                    </Button>
                  )}
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  {priceListRecords.data
                    ? `${priceListRecords.data.total} prikazanih jedinstvenih artikala od ${priceListRecords.data.source_record_count} izvornih redova`
                    : "Učitavanje sadržaja cenovnika…"}
                </Typography>
                <TableContainer sx={{ maxHeight: 520 }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Šifra proizvođača</TableCell>
                        <TableCell>EAN</TableCell>
                        <TableCell>Naziv</TableCell>
                        <TableCell align="right">Cena</TableCell>
                        <TableCell align="right">Ponavljanja</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(priceListRecords.data?.items ?? []).map((record, index) => (
                        <TableRow
                          hover
                          key={`${record.manufacturer_code ?? ""}-${record.ean ?? ""}-${record.name ?? ""}-${record.price ?? ""}-${index}`}
                          onClick={() => setOpenedRecord(record)}
                          sx={{ cursor: "pointer" }}
                        >
                          <TableCell>{record.manufacturer_code || "—"}</TableCell>
                          <TableCell>{record.ean || "—"}</TableCell>
                          <TableCell>{record.name || "—"}</TableCell>
                          <TableCell align="right">{record.price || "—"}</TableCell>
                          <TableCell align="right">
                            {record.duplicate_count}
                          </TableCell>
                        </TableRow>
                      ))}
                      {!priceListRecords.isLoading &&
                        !(priceListRecords.data?.items.length ?? 0) && (
                          <TableRow>
                            <TableCell colSpan={5} align="center">
                              Nema artikala koji odgovaraju pretrazi.
                            </TableCell>
                          </TableRow>
                        )}
                    </TableBody>
                  </Table>
                </TableContainer>
                <Stack direction="row" justifyContent="flex-end" gap={1}>
                  <Button
                    disabled={recordPage === 0 || priceListRecords.isFetching}
                    onClick={() => setRecordPage((value) => value - 1)}
                  >
                    Prethodna
                  </Button>
                  <Typography sx={{ alignSelf: "center" }}>
                    Strana {recordPage + 1}
                  </Typography>
                  <Button
                    disabled={
                      priceListRecords.isFetching ||
                      (recordPage + 1) * 25 >=
                        (priceListRecords.data?.total ?? 0)
                    }
                    onClick={() => setRecordPage((value) => value + 1)}
                  >
                    Sledeća
                  </Button>
                </Stack>
                <Button
                  variant="contained"
                  disabled={
                    !auth.can("mapping_profiles.write") ||
                    startMapping.isPending ||
                    !schemaFields.data?.total
                  }
                  onClick={() =>
                    startMapping.mutate({
                      profile: selectedSchema,
                      original_filename: String(selectedSchema.name),
                      detected_format: String(
                        selectedSchema.detected_format ?? "UNKNOWN"
                      ),
                      record_count: Number(
                        selectedSchema.baseline_record_count ?? 0
                      ),
                      sampled_record_count: 0,
                      fields: (schemaFields.data?.items ?? []).map((field) => ({
                        field: {
                          id: field.id,
                          position: Number(field.position),
                          name: String(field.name),
                          data_type: String(field.data_type),
                          nullable: Boolean(field.nullable)
                        },
                        sample_values: field.example_value
                          ? [String(field.example_value)]
                          : [],
                        confidence: 0
                      }))
                    })
                  }
                >
                  Mapiraj polja ovog cenovnika
                </Button>
              </Stack>
            </Paper>
          )}
        </Stack>
      ) : (
        <>
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
        </>
      )}
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
      <Dialog
        open={Boolean(analysis)}
        onClose={() => setAnalysis(null)}
        fullWidth
        maxWidth="lg"
      >
        <DialogTitle>Analiza cenovnika</DialogTitle>
        <DialogContent>
          {analysis && (
            <Stack gap={2}>
              <Typography variant="h6">
                {analysis.original_filename ?? "Preuzeti cenovnik"}
              </Typography>
              <Stack direction={{ xs: "column", sm: "row" }} gap={3}>
                <Typography>Format: {analysis.detected_format}</Typography>
                <Typography>Pronađeno proizvoda: {analysis.record_count}</Typography>
                <Typography>Pronađeno polja: {analysis.fields.length}</Typography>
                <Typography>Status: {String(analysis.profile.status)}</Typography>
              </Stack>
              <Typography color="text.secondary">
                Tehnički detalji strukture čuvaju se u pozadini. Sledeći korak
                je povezivanje pronađenih polja sa sistemskim poljima.
              </Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {analysis && (
            <Button
              variant="contained"
              disabled={startMapping.isPending}
              onClick={() => startMapping.mutate(analysis)}
            >
              Mapiraj polja
            </Button>
          )}
          <Button onClick={() => setAnalysis(null)}>Zatvori</Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={Boolean(openedRecord)}
        onClose={() => setOpenedRecord(null)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle>Podaci artikla iz cenovnika</DialogTitle>
        <DialogContent>
          <TableContainer>
            <Table size="small">
              <TableBody>
                {Object.entries(openedRecord?.values ?? {}).map(
                  ([field, value]) => (
                    <TableRow key={field}>
                      <TableCell sx={{ fontWeight: 700, width: "38%" }}>
                        {field}
                      </TableCell>
                      <TableCell sx={{ overflowWrap: "anywhere" }}>
                        <Typography
                          component="span"
                          variant="body2"
                          sx={{ whiteSpace: "pre-wrap" }}
                        >
                          {readableSupplierValue(value)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenedRecord(null)}>Zatvori</Button>
        </DialogActions>
      </Dialog>
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
      { key: "version_number", label: "Verzija", tooltip: "Nepromjenljiva poslovna verzija schema profila." },
      { key: "field_count", label: "Polja", tooltip: "Broj detektovanih aktivnih Schema Fields." }
    ],
    actions: [
      { name: "reanalyze", label: "Ponovo analiziraj izvor", tooltip: "Ponovo preuzima izvor i zamenjuje polja ove DRAFT verzije.", permission: "schema_profiles.write", icon: "retry" },
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
      { key: "total_record_count", label: "Zapisi", tooltip: "Ukupan broj pročitanih source redova." },
      { key: "failure_message", label: "Razlog neuspeha", tooltip: "Bezbedna poslovna poruka koju je sačuvao backend." }
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
