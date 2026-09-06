import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, InputLabel, LinearProgress, MenuItem, Paper, Select, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography
} from "@mui/material";
import { RefreshRounded, DeleteSweepRounded } from "@mui/icons-material";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../state/AuthContext";
import type { ApiError, CleanupAudit, CleanupPreview, SystemCapacity, SystemInventory } from "../types";
import { ArtifactArchivePanel } from "./system/ArtifactArchivePanel";

const bytes = (value: number | null | undefined) => {
  if (value == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toLocaleString("sr-RS", { maximumFractionDigits: 2 })} ${units[index]}`;
};

function CapacityCard({ title, value }: { title: string; value: SystemCapacity }) {
  return <Paper sx={{ p: 2.5, minWidth: 240, flex: 1 }}>
    <Stack direction="row" justifyContent="space-between" alignItems="center">
      <Typography color="text.secondary">{title}</Typography>
      <StatusChip value={value.status} />
    </Stack>
    <Typography variant="h4" mt={1}>{value.used_percent == null ? "—" : `${value.used_percent}%`}</Typography>
    <LinearProgress variant="determinate" value={value.used_percent ?? 0} color={value.status === "KRITIČNO" ? "error" : value.status === "UPOZORENJE" ? "warning" : "primary"} sx={{ my: 1.5, height: 8, borderRadius: 4 }} />
    <Typography variant="body2" color="text.secondary">{bytes(value.used_bytes)} od {bytes(value.total_bytes)}</Typography>
  </Paper>;
}

export function SystemPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [category, setCategory] = useState<"LOGOVI" | "PRIVREMENI_FAJLOVI">("LOGOVI");
  const [days, setDays] = useState(30);
  const inventory = useQuery({ queryKey: ["system-inventory"], queryFn: () => api<SystemInventory>("/system/resources") });
  const audit = useQuery({ queryKey: ["system-cleanup-audit"], queryFn: () => api<CleanupAudit[]>("/system/resources/cleanup/audit?limit=50") });
  const preview = useMutation({ mutationFn: () => api<CleanupPreview>("/system/resources/cleanup/preview", { method: "POST", body: { category, older_than_days: days } }) });
  const execute = useMutation({
    mutationFn: () => api<{ status: string; deleted_files: number; deleted_bytes: number }>("/system/resources/cleanup/execute", {
      method: "POST",
      body: { category, older_than_days: days, confirmation_token: preview.data!.confirmation_token }
    }),
    onSuccess: async () => {
      setDialogOpen(false);
      preview.reset();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["system-inventory"] }),
        queryClient.invalidateQueries({ queryKey: ["system-cleanup-audit"] })
      ]);
    }
  });
  const error = (inventory.error ?? audit.error ?? preview.error ?? execute.error) as ApiError | null;
  const data = inventory.data;

  return <Box>
    <PageHeader
      title="Sistem"
      description="Pregled resursa, rasta baze i skladišta. Poslovni podaci su zaštićeni od generičkog brisanja."
      actions={<Stack direction="row" gap={1}>
        <Button startIcon={<RefreshRounded />} onClick={() => inventory.refetch()}>Osveži</Button>
        {auth.can("system_resources.manage") && <Button variant="contained" color="warning" startIcon={<DeleteSweepRounded />} onClick={() => setDialogOpen(true)}>Bezbedno čišćenje</Button>}
      </Stack>}
    />
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error.message}</Alert>}
    <Stack direction={{ xs: "column", md: "row" }} gap={2} mb={2}>
      {data && <>
        <CapacityCard title="RAM memorija" value={data.runtime.memory} />
        <CapacityCard title="Disk" value={data.runtime.disk} />
        <Paper sx={{ p: 2.5, minWidth: 240, flex: 1 }}>
          <Typography color="text.secondary">Procesor</Typography>
          <Typography variant="h4" mt={1}>{data.runtime.processor_load_percent == null ? "—" : `${data.runtime.processor_load_percent}%`}</Typography>
          <Typography variant="body2" color="text.secondary" mt={2}>{data.runtime.processor_count} logičkih procesora</Typography>
        </Paper>
        <Paper sx={{ p: 2.5, minWidth: 240, flex: 1 }}>
          <Typography color="text.secondary">Baza podataka</Typography>
          <Typography variant="h4" mt={1}>{bytes(data.database_size_bytes)}</Typography>
          <Typography variant="body2" color="text.secondary" mt={2}>Informativno; nije dostupno za brisanje.</Typography>
        </Paper>
      </>}
    </Stack>
    <Typography variant="h2" mb={1.5}>Skladišta</Typography>
    <TableContainer component={Paper} sx={{ mb: 3 }}><Table>
      <TableHead><TableRow><TableCell>Kategorija</TableCell><TableCell>Veličina</TableCell><TableCell>Fajlovi</TableCell><TableCell>Status</TableCell><TableCell>Pravila</TableCell></TableRow></TableHead>
      <TableBody>{(data?.categories ?? []).map((item) => <TableRow key={item.code}>
        <TableCell><Typography fontWeight={700}>{item.label}</Typography></TableCell>
        <TableCell>{bytes(item.size_bytes)}</TableCell><TableCell>{item.file_count.toLocaleString("sr-RS")}</TableCell>
        <TableCell><StatusChip value={item.status} /></TableCell>
        <TableCell>{item.cleanup_allowed ? "Dozvoljeno kontrolisano čišćenje" : <Typography color="text.secondary">Zaštićeno — {item.protection_reason}</Typography>}</TableCell>
      </TableRow>)}</TableBody>
    </Table></TableContainer>
    <Typography variant="h2" mb={1.5}>Istorija čišćenja</Typography>
    <TableContainer component={Paper}><Table size="small">
      <TableHead><TableRow><TableCell>Datum</TableCell><TableCell>Kategorija</TableCell><TableCell>Starije od</TableCell><TableCell>Rezultat</TableCell><TableCell>Obrisano</TableCell><TableCell>Operator</TableCell></TableRow></TableHead>
      <TableBody>{(audit.data ?? []).map((item) => <TableRow key={item.id}><TableCell>{new Date(item.created_at).toLocaleString("sr-RS")}</TableCell><TableCell>{item.category}</TableCell><TableCell>{item.older_than_days} dana</TableCell><TableCell><StatusChip value={item.status} /></TableCell><TableCell>{item.deleted_files} / {bytes(item.deleted_bytes)}</TableCell><TableCell>{item.actor_id}</TableCell></TableRow>)}</TableBody>
    </Table></TableContainer>
    {auth.can("system_resources.manage") && <ArtifactArchivePanel />}
    <Dialog open={dialogOpen} onClose={() => { setDialogOpen(false); preview.reset(); }} fullWidth maxWidth="sm">
      <DialogTitle>Bezbedno čišćenje</DialogTitle><DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>Brisanje je ograničeno samo na dozvoljene direktorijume. Cenovnici, snapshot arhive, slike i podaci baze nisu obuhvaćeni.</Alert>
        <Stack gap={2} mt={1}>
          <FormControl><InputLabel>Kategorija</InputLabel><Select label="Kategorija" value={category} onChange={(event) => { setCategory(event.target.value as typeof category); preview.reset(); }}><MenuItem value="LOGOVI">Logovi aplikacije</MenuItem><MenuItem value="PRIVREMENI_FAJLOVI">Privremeni fajlovi</MenuItem></Select></FormControl>
          <TextField type="number" label="Obriši fajlove starije od (dana)" value={days} inputProps={{ min: 1, max: 3650 }} onChange={(event) => { setDays(Number(event.target.value)); preview.reset(); }} />
          {preview.data && <Alert severity="info">Pronađeno: {preview.data.candidate_files} fajlova, ukupno {bytes(preview.data.candidate_bytes)}. Potvrda važi do {new Date(preview.data.expires_at).toLocaleTimeString("sr-RS")}.</Alert>}
        </Stack>
      </DialogContent><DialogActions>
        <Button onClick={() => setDialogOpen(false)}>Otkaži</Button>
        {!preview.data ? <Button variant="contained" onClick={() => preview.mutate()} disabled={preview.isPending}>Pregledaj</Button> : <Button color="error" variant="contained" onClick={() => execute.mutate()} disabled={execute.isPending || preview.data.candidate_files === 0}>Potvrdi brisanje</Button>}
      </DialogActions>
    </Dialog>
  </Box>;
}
