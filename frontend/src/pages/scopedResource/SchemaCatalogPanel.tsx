import type { Dispatch, FormEvent, SetStateAction } from "react";
import { SearchRounded } from "@mui/icons-material";
import { Button, MenuItem, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";

import { StatusChip } from "../../components/StatusChip";
import type { Operation } from "../../types";
import type { PriceListRecord, PriceListRecordPage, SchemaAnalysis } from "./resourceModel";

type Props = {
  profiles: Operation[];
  profilesLoading: boolean;
  selectedSchemaId: string;
  selectedSchema?: Operation;
  fields: Operation[];
  records?: PriceListRecordPage;
  recordsLoading: boolean;
  recordsFetching: boolean;
  recordSearch: string;
  appliedRecordSearch: string;
  recordPage: number;
  mappingAllowed: boolean;
  mappingStarting: boolean;
  onSchemaId: (value: string) => void;
  onRecordSearch: (value: string) => void;
  onAppliedRecordSearch: (value: string) => void;
  setRecordPage: Dispatch<SetStateAction<number>>;
  onOpenRecord: (record: PriceListRecord) => void;
  onStartMapping: (analysis: SchemaAnalysis) => void;
};

export function SchemaCatalogPanel(props: Props) {
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    props.setRecordPage(0);
    props.onAppliedRecordSearch(props.recordSearch.trim());
  };
  const startMapping = () => {
    if (!props.selectedSchema) return;
    props.onStartMapping({
      profile: props.selectedSchema,
      original_filename: String(props.selectedSchema.name),
      detected_format: String(props.selectedSchema.detected_format ?? "UNKNOWN"),
      record_count: Number(props.selectedSchema.baseline_record_count ?? 0),
      sampled_record_count: 0,
      fields: props.fields.map((field) => ({
        field: { id: field.id, position: Number(field.position), name: String(field.name), data_type: String(field.data_type), nullable: Boolean(field.nullable) },
        sample_values: field.example_value ? [String(field.example_value)] : [], confidence: 0,
      })),
    });
  };
  return (
    <Stack gap={2}>
      <Typography color="text.secondary">Kliknite „Importuj cenovnik“ da sačuvate originalni fajl i analizirate njegova polja. Ranije preuzeti cenovnik možete izabrati ispod.</Typography>
      <TextField select size="small" label="Izaberite preuzeti cenovnik" value={props.selectedSchemaId} onChange={(event) => props.onSchemaId(event.target.value)} sx={{ maxWidth: 520 }}>
        {props.profilesLoading && <MenuItem disabled value="">Učitavanje preuzetih cenovnika…</MenuItem>}
        {!props.profilesLoading && !props.profiles.length && <MenuItem disabled value="">Nema uspešno preuzetih cenovnika za ovaj izvor</MenuItem>}
        {props.profiles.map((profile) => <MenuItem key={profile.id} value={profile.id}>{String(profile.name)} · {String(profile.status)} · {String(profile.baseline_record_count ?? 0)} proizvoda</MenuItem>)}
      </TextField>
      {props.selectedSchema && <Paper variant="outlined" sx={{ p: 2 }}><Stack gap={2}>
        <Stack direction={{ xs: "column", sm: "row" }} gap={3}>
          <Typography fontWeight={700}>{String(props.selectedSchema.name)}</Typography><Typography>Format: {String(props.selectedSchema.detected_format ?? "—")}</Typography><Typography>Proizvoda: {String(props.selectedSchema.baseline_record_count ?? 0)}</Typography><Typography>Polja: {String(props.selectedSchema.field_count ?? 0)}</Typography><StatusChip value={String(props.selectedSchema.status)} />
        </Stack>
        <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Polje u cenovniku</TableCell><TableCell>Primer sadržaja</TableCell><TableCell>Prepoznati tip</TableCell></TableRow></TableHead><TableBody>
          {props.fields.map((field) => <TableRow key={field.id}><TableCell>{String(field.name)}</TableCell><TableCell>{String(field.example_value ?? "—")}</TableCell><TableCell>{String(field.data_type)}</TableCell></TableRow>)}
        </TableBody></Table></TableContainer>
        <Typography variant="h6">Sadržaj cenovnika</Typography>
        <Typography color="text.secondary">Pretražite sve artikle po šifri proizvođača, EAN kodu, nazivu, ceni ili bilo kojoj drugoj vrednosti iz izvornog cenovnika.</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} gap={1} component="form" onSubmit={submitSearch}>
          <TextField size="small" label="Pretraži artikle" placeholder="Šifra, naziv, EAN ili cena" value={props.recordSearch} onChange={(event) => props.onRecordSearch(event.target.value)} sx={{ width: { xs: "100%", sm: 440 } }} />
          <Button type="submit" variant="outlined" startIcon={<SearchRounded />}>Pretraži</Button>
          {props.appliedRecordSearch && <Button onClick={() => { props.onRecordSearch(""); props.onAppliedRecordSearch(""); props.setRecordPage(0); }}>Obriši pretragu</Button>}
        </Stack>
        <Typography variant="body2" color="text.secondary">{props.records ? `${props.records.total} prikazanih jedinstvenih artikala od ${props.records.source_record_count} izvornih redova` : "Učitavanje sadržaja cenovnika…"}</Typography>
        <TableContainer sx={{ maxHeight: 520 }}><Table size="small" stickyHeader><TableHead><TableRow><TableCell>Šifra proizvođača</TableCell><TableCell>EAN</TableCell><TableCell>Naziv</TableCell><TableCell align="right">Cena</TableCell><TableCell align="right">Ponavljanja</TableCell></TableRow></TableHead><TableBody>
          {(props.records?.items ?? []).map((record, index) => <TableRow hover key={`${record.manufacturer_code ?? ""}-${record.ean ?? ""}-${record.name ?? ""}-${record.price ?? ""}-${index}`} onClick={() => props.onOpenRecord(record)} sx={{ cursor: "pointer" }}><TableCell>{record.manufacturer_code || "—"}</TableCell><TableCell>{record.ean || "—"}</TableCell><TableCell>{record.name || "—"}</TableCell><TableCell align="right">{record.price || "—"}</TableCell><TableCell align="right">{record.duplicate_count}</TableCell></TableRow>)}
          {!props.recordsLoading && !(props.records?.items.length ?? 0) && <TableRow><TableCell colSpan={5} align="center">Nema artikala koji odgovaraju pretrazi.</TableCell></TableRow>}
        </TableBody></Table></TableContainer>
        <Stack direction="row" justifyContent="flex-end" gap={1}><Button disabled={props.recordPage === 0 || props.recordsFetching} onClick={() => props.setRecordPage((value) => value - 1)}>Prethodna</Button><Typography sx={{ alignSelf: "center" }}>Strana {props.recordPage + 1}</Typography><Button disabled={props.recordsFetching || (props.recordPage + 1) * 25 >= (props.records?.total ?? 0)} onClick={() => props.setRecordPage((value) => value + 1)}>Sledeća</Button></Stack>
        <Button variant="contained" disabled={!props.mappingAllowed || props.mappingStarting || !props.fields.length} onClick={startMapping}>Mapiraj polja ovog cenovnika</Button>
      </Stack></Paper>}
    </Stack>
  );
}
