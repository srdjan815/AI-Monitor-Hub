import type { Dispatch, SetStateAction } from "react";
import { Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";

import type { Source, SupplierSchedule } from "../../types";
import { ALL_SUPPLIERS, dayNames, type ScheduleForm } from "./scheduleModel";

type SupplierOption = { id: string; supplier_code: string; company_name: string };
type Props = {
  open: boolean; editing: SupplierSchedule | null; supplierId: string; sourceId: string;
  suppliers: SupplierOption[]; sources: Source[]; allSourcesLoading: boolean; readyCount: number; skippedCount: number;
  form: ScheduleForm; saving: boolean;
  onClose: () => void; onSupplierId: (value: string) => void; onSourceId: (value: string) => void;
  setForm: Dispatch<SetStateAction<ScheduleForm>>; onSave: () => void;
};

export function ScheduleDialog(props: Props) {
  const allSuppliers = props.supplierId === ALL_SUPPLIERS;
  const disabled = props.saving || !props.supplierId || (allSuppliers ? props.allSourcesLoading || !props.readyCount : !props.sourceId);
  return <Dialog open={props.open} onClose={props.onClose} fullWidth maxWidth="md">
    <DialogTitle>{props.editing ? "Izmeni automatski raspored" : "Novi automatski raspored"}</DialogTitle><DialogContent><Stack gap={2} mt={1}>
      <FormControl fullWidth><InputLabel id="automation-supplier-label">Dobavljač</InputLabel><Select labelId="automation-supplier-label" label="Dobavljač" value={props.supplierId} disabled={Boolean(props.editing)} onChange={(event) => { props.onSupplierId(event.target.value); props.onSourceId(""); }}>{!props.editing && <MenuItem value={ALL_SUPPLIERS}>Svi dobavljači</MenuItem>}{props.suppliers.map((supplier) => <MenuItem key={supplier.id} value={supplier.id}>{supplier.supplier_code} · {supplier.company_name}</MenuItem>)}</Select></FormControl>
      <FormControl fullWidth disabled={!props.supplierId || allSuppliers || Boolean(props.editing)}><InputLabel id="automation-source-label">Konekcija</InputLabel><Select labelId="automation-source-label" label="Konekcija" value={props.sourceId} onChange={(event) => props.onSourceId(event.target.value)}>{allSuppliers && <MenuItem value="">Sve konekcije redom</MenuItem>}{props.sources.map((source) => <MenuItem key={source.id} value={source.id}>{source.source_code} · {source.name}</MenuItem>)}</Select></FormControl>
      {allSuppliers && <Alert severity="info">{props.allSourcesLoading ? "Učitavanje konekcija..." : `Raspored će dobiti ${props.readyCount} spremnih konekcija. ${props.skippedCount} nespremnih biće preskočeno i evidentirano u Incident centru. Worker obrađuje red jednu po jednu; neuspeh jedne ne zaustavlja ostale.`}</Alert>}
      <FormControl fullWidth><InputLabel id="automation-status-label">Status rasporeda</InputLabel><Select labelId="automation-status-label" label="Status rasporeda" value={props.form.status} onChange={(event) => props.setForm((value) => ({ ...value, status: event.target.value }))}><MenuItem value="ENABLED">Uključen</MenuItem><MenuItem value="PAUSED">Pauziran</MenuItem><MenuItem value="MANUAL">Samo ručno</MenuItem></Select></FormControl>
      {props.form.status !== "MANUAL" && <><FormControl fullWidth><InputLabel id="automation-type-label">Način ponavljanja</InputLabel><Select labelId="automation-type-label" label="Način ponavljanja" value={props.form.schedule_type} onChange={(event) => props.setForm((value) => ({ ...value, schedule_type: event.target.value }))}><MenuItem value="DAILY">Svakog dana</MenuItem><MenuItem value="MULTI_DAILY">Više puta dnevno</MenuItem><MenuItem value="INTERVAL">Na svakih N sati</MenuItem><MenuItem value="WEEKDAYS">Radnim danima</MenuItem><MenuItem value="WEEKLY">Izabrani dani u nedelji</MenuItem></Select></FormControl>
        {props.form.schedule_type === "INTERVAL" ? <TextField type="number" label="Interval u satima" value={props.form.interval_hours} inputProps={{ min: 1, max: 720 }} onChange={(event) => props.setForm((value) => ({ ...value, interval_hours: Number(event.target.value) }))} /> : <TextField label="Vreme pokretanja" value={props.form.times} helperText="Obavezan format je HH:MM. Za više termina koristite zarez, na primer: 08:30, 10:00, 12:00, 14:00 (bez tačke na kraju)." onChange={(event) => props.setForm((value) => ({ ...value, times: event.target.value }))} />}
        {props.form.schedule_type === "WEEKLY" && <Box><Typography variant="body2" mb={0.5}>Dani u nedelji</Typography><Stack direction="row" flexWrap="wrap">{dayNames.map((name, index) => <FormControlLabel key={name} label={name} control={<Checkbox checked={props.form.weekdays.includes(index + 1)} onChange={(event) => props.setForm((value) => ({ ...value, weekdays: event.target.checked ? [...value.weekdays, index + 1].sort() : value.weekdays.filter((day) => day !== index + 1) }))} />} />)}</Stack></Box>}
      </>}
      <FormControl fullWidth><InputLabel id="automation-depth-label">Dubina automatizacije</InputLabel><Select labelId="automation-depth-label" label="Dubina automatizacije" value={props.form.automation_depth} onChange={(event) => props.setForm((value) => ({ ...value, automation_depth: event.target.value }))}><MenuItem value="FETCH_ONLY">Samo preuzmi i sačuvaj</MenuItem><MenuItem value="FETCH_AND_ANALYZE">Preuzmi i analiziraj Schema</MenuItem><MenuItem value="FULL_PIPELINE">Kompletan pipeline do Snapshot-a i Delta-e</MenuItem></Select></FormControl>
      <Stack direction={{ xs: "column", sm: "row" }} gap={2}><TextField fullWidth type="number" label="Timeout u sekundama" value={props.form.timeout_seconds} onChange={(event) => props.setForm((value) => ({ ...value, timeout_seconds: Number(event.target.value) }))} /><TextField fullWidth type="number" label="Broj pokušaja" value={props.form.max_attempts} onChange={(event) => props.setForm((value) => ({ ...value, max_attempts: Number(event.target.value) }))} /></Stack>
    </Stack></DialogContent><DialogActions><Button onClick={props.onClose}>Otkaži</Button><Button variant="contained" disabled={disabled} onClick={props.onSave}>Sačuvaj raspored</Button></DialogActions>
  </Dialog>;
}
