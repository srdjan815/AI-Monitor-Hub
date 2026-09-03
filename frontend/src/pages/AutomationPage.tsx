import { useEffect, useMemo, useState } from "react";
import { PlayArrowRounded, ScheduleRounded } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { useSearchParams } from "react-router-dom";
import { supplierApi } from "../api/supplierApi";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import type { ApiError, Source, SupplierSchedule } from "../types";
import { normalizeScheduleTimes } from "./scheduleTime";
import { useAuth } from "../state/AuthContext";

const initialForm = {
  status: "ENABLED",
  schedule_type: "DAILY",
  times: "06:00",
  weekdays: [1, 2, 3, 4, 5] as number[],
  interval_hours: 6,
  automation_depth: "FULL_PIPELINE",
  timeout_seconds: 300,
  max_attempts: 3
};

const ALL_SUPPLIERS = "__all_suppliers__";

const dayNames = ["Ponedeljak", "Utorak", "Sreda", "Četvrtak", "Petak", "Subota", "Nedelja"];

export function AutomationPage() {
  const auth = useAuth();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [editing, setEditing] = useState<SupplierSchedule | null>(null);
  const [form, setForm] = useState(initialForm);
  useEffect(() => {
    const requestedSupplier = searchParams.get("supplier");
    const requestedSource = searchParams.get("source");
    if (requestedSupplier && requestedSource) {
      setSupplierId(requestedSupplier);
      setSourceId(requestedSource);
      setEditing(null);
      setForm(initialForm);
      setDialogOpen(true);
    }
  }, [searchParams]);
  const schedules = useQuery({
    queryKey: ["source-schedules"],
    queryFn: supplierApi.schedules
  });
  const suppliers = useQuery({
    queryKey: ["automation-suppliers"],
    queryFn: () => supplierApi.suppliers({ limit: 500, offset: 0, active_only: true })
  });
  const allSources = useQuery({
    queryKey: ["automation-all-sources", suppliers.data?.items.map((item) => item.id)],
    queryFn: async () => {
      const supplierRows = suppliers.data?.items ?? [];
      const pages = await Promise.all(
        supplierRows.map(async (supplier) => ({
          supplier,
          page: await supplierApi.sources(supplier.id, {
            limit: 500,
            offset: 0,
            active_only: true
          })
        }))
      );
      return pages
        .flatMap(({ supplier, page }) =>
          page.items.map((source) => ({ supplier, source }))
        )
        .sort((left, right) =>
          `${left.supplier.company_name}\u0000${left.source.name}`.localeCompare(
            `${right.supplier.company_name}\u0000${right.source.name}`,
            "sr"
          )
        );
    },
    enabled: supplierId === ALL_SUPPLIERS && Boolean(suppliers.data)
  });
  const sources = useQuery({
    queryKey: ["automation-sources", supplierId],
    queryFn: () =>
      supplierApi.sources(supplierId, {
        limit: 500,
        offset: 0,
        active_only: true
      }),
    enabled: Boolean(supplierId && supplierId !== ALL_SUPPLIERS)
  });
  const save = useMutation({
    mutationFn: async () => {
      const times = normalizeScheduleTimes(form.times);
      const payload = (version?: number) => ({
        version,
        status: form.status,
        schedule_type: form.status === "MANUAL" ? null : form.schedule_type,
        timezone: "Europe/Belgrade",
        times,
        weekdays: form.weekdays,
        interval_hours: form.interval_hours,
        automation_depth: form.automation_depth,
        timeout_seconds: form.timeout_seconds,
        max_attempts: form.max_attempts
      });
      if (supplierId !== ALL_SUPPLIERS) {
        await supplierApi.saveSchedule(
          supplierId,
          sourceId,
          payload(editing?.version)
        );
        return { saved: 1, skipped: 0, failed: [] as string[] };
      }
      const entries = allSources.data ?? [];
      let saved = 0;
      let skipped = 0;
      const failed: string[] = [];
      for (const { supplier, source } of entries) {
        if (source.status !== "ACTIVE") {
          try {
            await supplierApi.reportScheduleReadinessIncident(
              supplier.id,
              source.id
            );
            skipped += 1;
          } catch (error) {
            const apiError = error as ApiError;
            failed.push(
              `${supplier.company_name} / ${source.name}: ${apiError.message}`
            );
          }
          continue;
        }
        const existing = schedules.data?.items.find(
          (schedule) => schedule.source_connection_id === source.id
        );
        try {
          await supplierApi.saveSchedule(
            supplier.id,
            source.id,
            payload(existing?.version)
          );
          saved += 1;
        } catch (error) {
          const apiError = error as ApiError;
          failed.push(
            `${supplier.company_name} / ${source.name}: ${apiError.message}`
          );
        }
      }
      return { saved, skipped, failed };
    },
    onSuccess: ({ saved, skipped, failed }) => {
      if (saved > 0) {
        toast.success(
          saved === 1
          ? "Automatski raspored je sačuvan."
          : `Sačuvani su rasporedi za ${saved} konekcija.`
        );
      }
      if (skipped > 0) {
        toast(
          `${skipped} nespremnih konekcija je preskočeno; upozorenje je upisano u Incident centar.`,
          { duration: 8000, icon: "⚠️" }
        );
      }
      if (failed.length > 0) {
        const visibleFailures = failed.slice(0, 3).join(" | ");
        const remaining = failed.length > 3 ? ` | i još ${failed.length - 3}` : "";
        toast.error(
          `Nije sačuvano ${failed.length}: ${visibleFailures}${remaining}`,
          { duration: 12000 }
        );
      } else {
        setDialogOpen(false);
      }
      queryClient.invalidateQueries({ queryKey: ["source-schedules"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });
  const runNow = useMutation({
    mutationFn: (row: SupplierSchedule) =>
      supplierApi.runPipelineNow(
        row.supplier_id!,
        row.source_connection_id,
        row.automation_depth
      ),
    onSuccess: (run) => {
      toast.success(`${run.pipeline_code} je dodat u red za izvršavanje.`);
      queryClient.invalidateQueries({ queryKey: ["source-schedules"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const columns = useMemo<Column<SupplierSchedule>[]>(
    () => [
      {
        key: "supplier_name",
        label: "Dobavljač",
        tooltip: "Dobavljač čiji će se cenovnik automatski obrađivati.",
        render: (row) => <Typography fontWeight={700}>{row.supplier_name}</Typography>,
        csv: (row) => row.supplier_name
      },
      {
        key: "source_name",
        label: "Konekcija",
        tooltip: "Aktivna Source Connection konfiguracija.",
        render: (row) => `${row.source_code} · ${row.source_name}`,
        csv: (row) => row.source_name
      },
      {
        key: "status",
        label: "Raspored",
        tooltip: "ENABLED se izvršava automatski; PAUSED i MANUAL ne pokreću zadatke.",
        render: (row) => <StatusChip value={row.status} />,
        csv: (row) => row.status
      },
      {
        key: "automation_depth",
        label: "Obrada",
        tooltip: "Dubina automatskog Supplier Pipeline-a.",
        render: (row) =>
          row.automation_depth === "FULL_PIPELINE"
            ? "Kompletan pipeline"
            : row.automation_depth === "FETCH_AND_ANALYZE"
              ? "Preuzmi i analiziraj"
              : "Samo preuzmi",
        csv: (row) => row.automation_depth
      },
      {
        key: "next_run_at",
        label: "Sledeće pokretanje",
        tooltip: "Sledeći termin izračunat u vremenskoj zoni Europe/Belgrade.",
        render: (row) =>
          row.next_run_at
            ? new Date(row.next_run_at).toLocaleString("sr-RS")
            : "Nije zakazano",
        csv: (row) => row.next_run_at
      },
      {
        key: "last_result",
        label: "Poslednji rezultat",
        tooltip: "Rezultat poslednjeg planiranog izvršavanja.",
        render: (row) => (
          <Stack gap={0.25}>
            <StatusChip value={row.last_result ?? "PENDING"} />
            <Typography variant="caption" color="text.secondary">
              {row.last_duration_ms == null
                ? "Nema merenja"
                : `${(row.last_duration_ms / 1000).toFixed(1)} s · ${row.consecutive_failures} uzastopnih grešaka`}
            </Typography>
          </Stack>
        ),
        csv: (row) => row.last_result
      }
    ],
    []
  );

  const openNew = () => {
    setEditing(null);
    setSupplierId("");
    setSourceId("");
    setForm(initialForm);
    setDialogOpen(true);
  };
  const openEdit = (row: SupplierSchedule) => {
    setEditing(row);
    setSupplierId(row.supplier_id ?? "");
    setSourceId(row.source_connection_id);
    setForm({
      status: row.status,
      schedule_type: row.schedule_type ?? "DAILY",
      times: (row.schedule_configuration.times ?? ["06:00"]).join(", "),
      weekdays: row.schedule_configuration.weekdays ?? [1, 2, 3, 4, 5],
      interval_hours: row.schedule_configuration.interval_hours ?? 6,
      automation_depth: row.automation_depth,
      timeout_seconds: row.timeout_seconds,
      max_attempts: row.max_attempts
    });
    setDialogOpen(true);
  };

  return (
    <>
      <PageHeader
        title="Automatski pokretač"
        description="Trajni nedeljni raspored preuzimanja, validacije, importa i Snapshot obrade."
        actions={
          auth.can("supplier_sources.write") ? (
            <Button variant="contained" startIcon={<ScheduleRounded />} onClick={openNew}>
              Dodaj raspored
            </Button>
          ) : undefined
        }
      />
      <Alert severity="info" sx={{ mb: 2 }}>
        Rasporedi preživljavaju restart. Isti izvor se nikada ne izvršava paralelno.
      </Alert>
      <EntityTable
        tableId="source-schedules"
        columns={columns}
        rows={schedules.data?.items ?? []}
        total={schedules.data?.total ?? 0}
        page={page}
        pageSize={500}
        loading={schedules.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={auth.can("supplier_sources.write") ? openEdit : undefined}
        onRefresh={() => schedules.refetch()}
        bulkActions={
          selected.length === 1 && auth.can("acquisitions.execute") ? (
            <Tooltip title="Odmah pokreni izabrani raspored bez menjanja sledećeg termina.">
              <Button
                size="small"
                startIcon={<PlayArrowRounded />}
                disabled={runNow.isPending}
                onClick={() => {
                  const row = schedules.data?.items.find((item) => item.id === selected[0]);
                  if (row) runNow.mutate(row);
                }}
              >
                Pokreni sada
              </Button>
            </Tooltip>
          ) : undefined
        }
      />
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>{editing ? "Izmeni automatski raspored" : "Novi automatski raspored"}</DialogTitle>
        <DialogContent>
          <Stack gap={2} mt={1}>
            <FormControl fullWidth>
              <InputLabel id="automation-supplier-label">Dobavljač</InputLabel>
              <Select
                labelId="automation-supplier-label"
                label="Dobavljač"
                value={supplierId}
                disabled={Boolean(editing)}
                onChange={(event) => {
                  setSupplierId(event.target.value);
                  setSourceId("");
                }}
              >
                {!editing && (
                  <MenuItem value={ALL_SUPPLIERS}>Svi dobavljači</MenuItem>
                )}
                {suppliers.data?.items.map((supplier) => (
                  <MenuItem key={supplier.id} value={supplier.id}>
                    {supplier.supplier_code} · {supplier.company_name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl
              fullWidth
              disabled={
                !supplierId ||
                supplierId === ALL_SUPPLIERS ||
                Boolean(editing)
              }
            >
              <InputLabel id="automation-source-label">Konekcija</InputLabel>
              <Select
                labelId="automation-source-label"
                label="Konekcija"
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
              >
                {supplierId === ALL_SUPPLIERS && (
                  <MenuItem value="">Sve konekcije redom</MenuItem>
                )}
                {sources.data?.items.map((source: Source) => (
                  <MenuItem key={source.id} value={source.id}>
                    {source.source_code} · {source.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {supplierId === ALL_SUPPLIERS && (
              <Alert severity="info">
                {allSources.isLoading
                  ? "Učitavanje konekcija..."
                  : `Raspored će dobiti ${(allSources.data ?? []).filter(({ source }) => source.status === "ACTIVE").length} spremnih konekcija. ${(allSources.data ?? []).filter(({ source }) => source.status !== "ACTIVE").length} nespremnih biće preskočeno i evidentirano u Incident centru. Worker obrađuje red jednu po jednu; neuspeh jedne ne zaustavlja ostale.`}
              </Alert>
            )}
            <FormControl fullWidth>
              <InputLabel id="automation-status-label">Status rasporeda</InputLabel>
              <Select
                labelId="automation-status-label"
                label="Status rasporeda"
                value={form.status}
                onChange={(event) => setForm((value) => ({ ...value, status: event.target.value }))}
              >
                <MenuItem value="ENABLED">Uključen</MenuItem>
                <MenuItem value="PAUSED">Pauziran</MenuItem>
                <MenuItem value="MANUAL">Samo ručno</MenuItem>
              </Select>
            </FormControl>
            {form.status !== "MANUAL" && (
              <>
                <FormControl fullWidth>
                  <InputLabel id="automation-type-label">Način ponavljanja</InputLabel>
                  <Select
                    labelId="automation-type-label"
                    label="Način ponavljanja"
                    value={form.schedule_type}
                    onChange={(event) =>
                      setForm((value) => ({ ...value, schedule_type: event.target.value }))
                    }
                  >
                    <MenuItem value="DAILY">Svakog dana</MenuItem>
                    <MenuItem value="MULTI_DAILY">Više puta dnevno</MenuItem>
                    <MenuItem value="INTERVAL">Na svakih N sati</MenuItem>
                    <MenuItem value="WEEKDAYS">Radnim danima</MenuItem>
                    <MenuItem value="WEEKLY">Izabrani dani u nedelji</MenuItem>
                  </Select>
                </FormControl>
                {form.schedule_type === "INTERVAL" ? (
                  <TextField
                    type="number"
                    label="Interval u satima"
                    value={form.interval_hours}
                    inputProps={{ min: 1, max: 720 }}
                    onChange={(event) =>
                      setForm((value) => ({
                        ...value,
                        interval_hours: Number(event.target.value)
                      }))
                    }
                  />
                ) : (
                  <TextField
                    label="Vreme pokretanja"
                    value={form.times}
                    helperText="Obavezan format je HH:MM. Za više termina koristite zarez, na primer: 08:30, 10:00, 12:00, 14:00 (bez tačke na kraju)."
                    onChange={(event) =>
                      setForm((value) => ({ ...value, times: event.target.value }))
                    }
                  />
                )}
                {form.schedule_type === "WEEKLY" && (
                  <Box>
                    <Typography variant="body2" mb={0.5}>Dani u nedelji</Typography>
                    <Stack direction="row" flexWrap="wrap">
                      {dayNames.map((name, index) => (
                        <FormControlLabel
                          key={name}
                          label={name}
                          control={
                            <Checkbox
                              checked={form.weekdays.includes(index + 1)}
                              onChange={(event) =>
                                setForm((value) => ({
                                  ...value,
                                  weekdays: event.target.checked
                                    ? [...value.weekdays, index + 1].sort()
                                    : value.weekdays.filter((day) => day !== index + 1)
                                }))
                              }
                            />
                          }
                        />
                      ))}
                    </Stack>
                  </Box>
                )}
              </>
            )}
            <FormControl fullWidth>
              <InputLabel id="automation-depth-label">Dubina automatizacije</InputLabel>
              <Select
                labelId="automation-depth-label"
                label="Dubina automatizacije"
                value={form.automation_depth}
                onChange={(event) =>
                  setForm((value) => ({ ...value, automation_depth: event.target.value }))
                }
              >
                <MenuItem value="FETCH_ONLY">Samo preuzmi i sačuvaj</MenuItem>
                <MenuItem value="FETCH_AND_ANALYZE">Preuzmi i analiziraj Schema</MenuItem>
                <MenuItem value="FULL_PIPELINE">Kompletan pipeline do Snapshot-a i Delta-e</MenuItem>
              </Select>
            </FormControl>
            <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
              <TextField
                fullWidth
                type="number"
                label="Timeout u sekundama"
                value={form.timeout_seconds}
                onChange={(event) =>
                  setForm((value) => ({
                    ...value,
                    timeout_seconds: Number(event.target.value)
                  }))
                }
              />
              <TextField
                fullWidth
                type="number"
                label="Broj pokušaja"
                value={form.max_attempts}
                onChange={(event) =>
                  setForm((value) => ({
                    ...value,
                    max_attempts: Number(event.target.value)
                  }))
                }
              />
            </Stack>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Otkaži</Button>
          <Button
            variant="contained"
            disabled={
              save.isPending ||
              !supplierId ||
              (supplierId === ALL_SUPPLIERS
                ? allSources.isLoading || !allSources.data?.length
                : !sourceId)
            }
            onClick={() => save.mutate()}
          >
            Sačuvaj raspored
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
