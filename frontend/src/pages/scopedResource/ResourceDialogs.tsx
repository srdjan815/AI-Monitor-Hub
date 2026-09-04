import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Table, TableBody, TableCell, TableContainer, TableRow, Typography } from "@mui/material";

import { readableSupplierValue, type PriceListRecord, type SchemaAnalysis } from "./resourceModel";

export function SchemaAnalysisDialog({ analysis, startingMapping, onClose, onStartMapping }: { analysis: SchemaAnalysis | null; startingMapping: boolean; onClose: () => void; onStartMapping: (analysis: SchemaAnalysis) => void }) {
  return (
    <Dialog open={Boolean(analysis)} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle>Analiza cenovnika</DialogTitle>
      <DialogContent>{analysis && <Stack gap={2}>
        <Typography variant="h6">{analysis.original_filename ?? "Preuzeti cenovnik"}</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} gap={3}>
          <Typography>Format: {analysis.detected_format}</Typography><Typography>Pronađeno proizvoda: {analysis.record_count}</Typography><Typography>Pronađeno polja: {analysis.fields.length}</Typography><Typography>Status: {String(analysis.profile.status)}</Typography>
        </Stack>
        <Typography color="text.secondary">Tehnički detalji strukture čuvaju se u pozadini. Sledeći korak je povezivanje pronađenih polja sa sistemskim poljima.</Typography>
      </Stack>}</DialogContent>
      <DialogActions>{analysis && <Button variant="contained" disabled={startingMapping} onClick={() => onStartMapping(analysis)}>Mapiraj polja</Button>}<Button onClick={onClose}>Zatvori</Button></DialogActions>
    </Dialog>
  );
}

export function PriceListRecordDialog({ record, onClose }: { record: PriceListRecord | null; onClose: () => void }) {
  return (
    <Dialog open={Boolean(record)} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Podaci artikla iz cenovnika</DialogTitle>
      <DialogContent><TableContainer><Table size="small"><TableBody>
        {Object.entries(record?.values ?? {}).map(([field, value]) => <TableRow key={field}><TableCell sx={{ fontWeight: 700, width: "38%" }}>{field}</TableCell><TableCell sx={{ overflowWrap: "anywhere" }}><Typography component="span" variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{readableSupplierValue(value)}</Typography></TableCell></TableRow>)}
      </TableBody></Table></TableContainer></DialogContent>
      <DialogActions><Button onClick={onClose}>Zatvori</Button></DialogActions>
    </Dialog>
  );
}
