import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, FormControl, FormControlLabel, InputLabel, MenuItem, Paper, Select, Stack, Switch, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { ApiError, RetentionPolicy, RetentionPreview, RetentionRun } from "../../types";

const bytes = (value: number) => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount.toLocaleString("sr-RS", { maximumFractionDigits: 2 })} ${units[index]}`;
};

export function DataRetentionPanel() {
  const queryClient = useQueryClient();
  const policies = useQuery({ queryKey: ["retention-policies"], queryFn: () => api<{ items: RetentionPolicy[]; total: number }>("/system/resources/data-retention/policies") });
  const runs = useQuery({ queryKey: ["retention-runs"], queryFn: () => api<RetentionRun[]>("/system/resources/data-retention/runs?limit=20") });
  const [sourceId, setSourceId] = useState("");
  const selected = policies.data?.items.find((item) => item.source_connection_id === sourceId);
  const [stagingDays, setStagingDays] = useState(30);
  const [snapshotDays, setSnapshotDays] = useState(90);
  const [minimumSnapshots, setMinimumSnapshots] = useState(7);
  const [batchSize, setBatchSize] = useState(1000);
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (!sourceId && policies.data?.items.length) setSourceId(policies.data.items[0].source_connection_id);
  }, [policies.data, sourceId]);
  useEffect(() => {
    if (!selected) return;
    setStagingDays(selected.staging_retention_days); setSnapshotDays(selected.snapshot_online_days);
    setMinimumSnapshots(selected.minimum_online_snapshots); setBatchSize(selected.cleanup_batch_size); setEnabled(selected.enabled);
  }, [selected]);
  const refresh = async () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ["retention-policies"] }),
    queryClient.invalidateQueries({ queryKey: ["retention-runs"] }),
  ]);
  const save = useMutation({
    mutationFn: () => api<RetentionPolicy>(`/system/resources/data-retention/policies/${sourceId}`, { method: "PUT", body: { enabled, staging_retention_days: stagingDays, snapshot_online_days: snapshotDays, minimum_online_snapshots: minimumSnapshots, cleanup_batch_size: batchSize, expected_version: selected?.version ?? null } }),
    onSuccess: refresh,
  });
  const preview = useMutation({ mutationFn: () => api<RetentionPreview>(`/system/resources/data-retention/policies/${sourceId}/preview`, { method: "POST" }), onSuccess: refresh });
  const error = (policies.error || runs.error || save.error || preview.error) as ApiError | null;
  const result = preview.data;
  return <Paper sx={{ p: 2.5, mt: 3 }}>
    <Typography variant="h2">Kontrola rasta podataka</Typography>
    <Typography color="text.secondary">Analiza po dobavljačkom izvoru. Pregled ništa ne briše; statistička istorija ostaje trajno sačuvana.</Typography>
    {error && <Alert severity="error" sx={{ mt: 2 }}>{error.message}</Alert>}
    <Stack direction={{ xs: "column", lg: "row" }} gap={2} my={2} flexWrap="wrap">
      <FormControl sx={{ minWidth: 300, flex: 1 }}><InputLabel>Dobavljač / izvor</InputLabel><Select label="Dobavljač / izvor" value={sourceId} onChange={(event) => { setSourceId(event.target.value); preview.reset(); }}>{(policies.data?.items ?? []).map((item) => <MenuItem key={item.source_connection_id} value={item.source_connection_id}>{item.supplier_name} — {item.source_name}</MenuItem>)}</Select></FormControl>
      <TextField label="Staging (dana)" type="number" value={stagingDays} onChange={(event) => setStagingDays(Number(event.target.value))} inputProps={{ min: 1, max: 3650 }} />
      <TextField label="Snapshot online (dana)" type="number" value={snapshotDays} onChange={(event) => setSnapshotDays(Number(event.target.value))} inputProps={{ min: 1, max: 3650 }} />
      <TextField label="Minimalno snapshotova" type="number" value={minimumSnapshots} onChange={(event) => setMinimumSnapshots(Number(event.target.value))} inputProps={{ min: 2, max: 100 }} />
      <TextField label="Veličina serije" type="number" value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} inputProps={{ min: 1, max: 10000 }} />
      <FormControlLabel control={<Switch checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />} label="Politika uključena" />
    </Stack>
    <Stack direction="row" gap={1}><Button variant="contained" onClick={() => save.mutate()} disabled={!sourceId || save.isPending}>Sačuvaj politiku</Button><Button onClick={() => preview.mutate()} disabled={!selected?.configured || preview.isPending}>Analiziraj bez brisanja</Button></Stack>
    {result && <Stack gap={1} mt={2}>
      <Alert severity="info">Staging kandidati: {result.candidate_staging_rows.toLocaleString("sr-RS")} ({bytes(result.candidate_staging_bytes)}); sa aktivnim referencama: {result.referenced_staging_rows.toLocaleString("sr-RS")}.</Alert>
      <Alert severity={result.blockers.length ? "warning" : "success"}>Snapshot kandidati: {result.candidate_snapshots}; stavke: {result.candidate_snapshot_items.toLocaleString("sr-RS")} ({bytes(result.candidate_snapshot_bytes)}). Statistički sačuvano: {result.observations_preserved.toLocaleString("sr-RS")}. Spremno za offload: {result.snapshots_ready_for_offload}; prvo arhivirati: {result.snapshots_requiring_archive}; zaštićeno: {result.protected_snapshots}.</Alert>
      {result.blockers.map((item) => <Alert key={item} severity="warning">{item}</Alert>)}
      <Button color="warning" variant="contained" disabled>Arhiviraj i očisti — zaključano zaštitnim proverama</Button>
    </Stack>}
    <Typography variant="h3" mt={3} mb={1}>Istorija analiza</Typography>
    <Table size="small"><TableHead><TableRow><TableCell>Datum</TableCell><TableCell>Izvor</TableCell><TableCell>Status</TableCell><TableCell>Staging kandidati</TableCell><TableCell>Snapshot kandidati</TableCell><TableCell>Operator</TableCell></TableRow></TableHead><TableBody>{(runs.data ?? []).map((run) => <TableRow key={run.id}><TableCell>{new Date(run.created_at).toLocaleString("sr-RS")}</TableCell><TableCell>{run.source_name}</TableCell><TableCell>{run.status}</TableCell><TableCell>{run.candidate_staging_rows.toLocaleString("sr-RS")}</TableCell><TableCell>{run.candidate_snapshots}</TableCell><TableCell>{run.created_by}</TableCell></TableRow>)}</TableBody></Table>
  </Paper>;
}
