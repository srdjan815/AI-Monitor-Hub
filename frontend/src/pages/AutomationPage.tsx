import { useEffect, useMemo, useState } from "react";
import { PlayArrowRounded, ScheduleRounded } from "@mui/icons-material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Stack,
  Tooltip,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { useSearchParams } from "react-router-dom";
import { supplierApi } from "../api/supplierApi";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import type { ApiError, SupplierSchedule } from "../types";
import { normalizeScheduleTimes } from "./scheduleTime";
import { useAuth } from "../state/AuthContext";

import { ScheduleDialog } from "./automation/ScheduleDialog";
import { ALL_SUPPLIERS, initialScheduleForm as initialForm } from "./automation/scheduleModel";

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
      <ScheduleDialog
        open={dialogOpen}
        editing={editing}
        supplierId={supplierId}
        sourceId={sourceId}
        suppliers={suppliers.data?.items ?? []}
        sources={sources.data?.items ?? []}
        allSourcesLoading={allSources.isLoading}
        readyCount={(allSources.data ?? []).filter(({ source }) => source.status === "ACTIVE").length}
        skippedCount={(allSources.data ?? []).filter(({ source }) => source.status !== "ACTIVE").length}
        form={form}
        saving={save.isPending}
        onClose={() => setDialogOpen(false)}
        onSupplierId={setSupplierId}
        onSourceId={setSourceId}
        setForm={setForm}
        onSave={() => save.mutate()}
      />
    </>
  );
}
