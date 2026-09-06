import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, FormControlLabel, Paper, Stack, Switch, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import { StatusChip } from "../../components/StatusChip";
import type { ArtifactArchiveStatus } from "../../types";
import { archivePathError, operationErrorMessage } from "./artifactArchiveValidation";

const bytes = (value: number) => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount.toLocaleString("sr-RS", { maximumFractionDigits: 2 })} ${units[index]}`;
};

export function ArtifactArchivePanel() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["artifact-archive"], queryFn: () => api<ArtifactArchiveStatus>("/system/resources/artifact-archive") });
  const [name, setName] = useState("Primarna NAS arhiva");
  const [path, setPath] = useState("cenovnici");
  const [days, setDays] = useState(30);
  const [enabled, setEnabled] = useState(false);
  const pathError = archivePathError(path);
  useEffect(() => {
    const item = status.data?.setting;
    if (item) { setName(item.display_name); setPath(item.relative_path); setDays(item.local_retention_days); setEnabled(item.enabled); }
  }, [status.data?.setting]);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["artifact-archive"] });
  const save = useMutation({ mutationFn: () => api("/system/resources/artifact-archive/setting", { method: "PUT", body: { display_name: name.trim(), relative_path: path.trim(), enabled, local_retention_days: days, expected_version: status.data?.setting?.version ?? null } }), onSuccess: refresh });
  const test = useMutation({ mutationFn: () => api<{ status: string; message: string }>("/system/resources/artifact-archive/test", { method: "POST" }), onSuccess: refresh });
  const process = useMutation({ mutationFn: () => api<{ attempted: number; verified: number; failed: number }>("/system/resources/artifact-archive/process?limit=25", { method: "POST" }), onSuccess: refresh });
  const data = status.data;
  const operationError = save.error || test.error || process.error;
  return <Paper sx={{ p: 2.5, mt: 3 }}>
    <Stack direction={{ xs: "column", lg: "row" }} justifyContent="space-between" gap={2}><div><Typography variant="h2">Arhiva originalnih cenovnika</Typography><Typography color="text.secondary">NAS/SMB ili NFS se montira na server; aplikacija koristi ograničenu relativnu putanju i proverava SHA-256.</Typography></div>{data?.setting?.last_test_status && <StatusChip value={data.setting.last_test_status} />}</Stack>
    <Stack direction="row" gap={2} my={2} flexWrap="wrap" alignItems="flex-start">
      <TextField label="Naziv odredišta" value={name} onChange={(event) => setName(event.target.value)} sx={{ flex: "1 1 360px" }} />
      <TextField label="Podfolder u montiranoj arhivi" value={path} onChange={(event) => setPath(event.target.value)} error={Boolean(pathError)} sx={{ flex: "1 1 360px" }} helperText={pathError ?? "Primer: cenovnici ili cenovnici/2026. Lokaciju na C: disku podešava administrator servera."} />
      <TextField label="Lokalno zadržavanje (dana)" type="number" value={days} onChange={(event) => setDays(Number(event.target.value))} inputProps={{ min: 1, max: 3650 }} helperText="Brisanje nije aktivno dok kopija nije verifikovana" sx={{ flex: "0 1 300px", minWidth: 260 }} />
      <FormControlLabel sx={{ minWidth: 175, minHeight: 56, m: 0 }} control={<Switch checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />} label="Automatski prenos" />
    </Stack>
    <Stack direction="row" gap={1} flexWrap="wrap"><Button variant="contained" onClick={() => save.mutate()} disabled={save.isPending || Boolean(pathError) || !name.trim()}>Sačuvaj</Button><Button onClick={() => test.mutate()} disabled={!data?.setting || test.isPending}>Testiraj odredište</Button><Button onClick={() => process.mutate()} disabled={!data?.setting?.enabled || process.isPending}>Obradi sledećih 25</Button></Stack>
    {data && <Alert severity={data.failed_transfers ? "warning" : "info"} sx={{ mt: 2 }}>Na čekanju: {data.pending_transfers}. Verifikovano: {data.verified_transfers} ({bytes(data.verified_bytes)}). Neuspešno: {data.failed_transfers}. Lokalni duplikati: {data.duplicate_artifacts} ({bytes(data.duplicate_bytes)}).</Alert>}
    {operationError && <Alert severity="error" sx={{ mt: 1 }}>{operationErrorMessage(operationError)}</Alert>}
    {test.data && <Alert severity={test.data.status === "SUCCEEDED" ? "success" : "error"} sx={{ mt: 1 }}>{test.data.message}</Alert>}
    {process.data && <Alert severity={process.data.failed ? "warning" : "success"} sx={{ mt: 1 }}>Pokušano {process.data.attempted}, verifikovano {process.data.verified}, neuspešno {process.data.failed}.</Alert>}
  </Paper>;
}
