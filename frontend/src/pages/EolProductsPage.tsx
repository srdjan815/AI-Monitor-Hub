import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel,
  MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography
} from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { PageHeader } from "../components/PageHeader";
import { useAuth } from "../state/AuthContext";
import type { ApiError } from "../types";

const monthOptions = Array.from({ length: 12 }, (_, index) => index + 1);
const statusLabels = {
  EOL_CANDIDATE: "EOL kandidat",
  MARKED_FOR_DEACTIVATION: "Označen za deaktivaciju",
  DEACTIVATED: "Deaktiviran"
};

export function EolProductsPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [months, setMonths] = useState(6);
  const [supplierId, setSupplierId] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [website, setWebsite] = useState(true);
  const [pantheon, setPantheon] = useState(true);

  const suppliers = useQuery({
    queryKey: ["eol-suppliers"],
    queryFn: () => supplierApi.suppliers({ limit: 500, offset: 0 })
  });
  const candidates = useQuery({
    queryKey: ["eol-products", months, supplierId, search],
    queryFn: () => supplierApi.eolProducts({
      inactivity_months: months, supplier_id: supplierId, search,
      limit: 500, offset: 0
    })
  });
  const eligible = useMemo(
    () => (candidates.data?.items ?? []).filter((item) => item.export_eligible),
    [candidates.data]
  );
  const allSelected = eligible.length > 0 && eligible.every((item) => selected.includes(item.identity_key));
  const prepare = useMutation({
    mutationFn: () => supplierApi.prepareEolDeactivation({
      identity_keys: selected,
      inactivity_months: months,
      target_systems: [website && "WEBSITE", pantheon && "PANTHEON"].filter(Boolean),
      idempotency_key: `ui-eol-${crypto.randomUUID()}`
    }),
    onSuccess: async () => {
      setConfirmOpen(false);
      setSelected([]);
      await queryClient.invalidateQueries({ queryKey: ["eol-products"] });
    }
  });
  const error = (candidates.error ?? prepare.error) as ApiError | null;

  const toggle = (key: string) => setSelected((current) =>
    current.includes(key) ? current.filter((value) => value !== key) : [...current, key]
  );

  return <Box>
    <PageHeader
      title="EOL artikli"
      description="Artikli koji se izabrani broj meseci nisu pojavili kao aktivni ni kod jednog dobavljača. Istorija ostaje trajno sačuvana."
      actions={auth.can("eol_products.manage") ?
        <Button variant="contained" disabled={selected.length === 0} onClick={() => setConfirmOpen(true)}>
          Pripremi deaktivaciju ({selected.length})
        </Button> : undefined}
    />
    <Paper sx={{ p: 2, mb: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} gap={2}>
        <FormControl size="small" sx={{ minWidth: 210 }}>
          <InputLabel>Period neaktivnosti</InputLabel>
          <Select value={months} label="Period neaktivnosti" onChange={(event) => { setMonths(Number(event.target.value)); setSelected([]); }}>
            {monthOptions.map((value) => <MenuItem key={value} value={value}>{value} {value === 1 ? "mesec" : "meseci"}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 240 }}>
          <InputLabel>Dobavljač</InputLabel>
          <Select value={supplierId} label="Dobavljač" onChange={(event) => { setSupplierId(event.target.value); setSelected([]); }}>
            <MenuItem value="">Svi dobavljači</MenuItem>
            {(suppliers.data?.items ?? []).map((supplier) => <MenuItem key={supplier.id} value={supplier.id}>{supplier.company_name}</MenuItem>)}
          </Select>
        </FormControl>
        <TextField size="small" label="EAN, naziv ili šifra" value={search} onChange={(event) => setSearch(event.target.value)} sx={{ minWidth: 280 }} />
      </Stack>
    </Paper>
    <Alert severity="info" sx={{ mb: 2 }}>
      Nestanak kod samo jednog dobavljača nije EOL. Artikal ulazi na ovu listu tek kada nije aktivan ni u jednoj dobavljačkoj ponudi.
    </Alert>
    {error && <Alert severity="error" sx={{ mb: 2 }}>{error.message}</Alert>}
    {prepare.isSuccess && <Alert severity="success" sx={{ mb: 2 }}>Kreiran je kontrolisani paket {prepare.data.batch_code}. Spoljna deaktivacija još nije izvršena.</Alert>}
    <TableContainer component={Paper}>
      <Table>
        <TableHead><TableRow>
          <TableCell padding="checkbox"><Checkbox checked={allSelected} onChange={() => setSelected(allSelected ? [] : eligible.map((item) => item.identity_key))} /></TableCell>
          <TableCell>Artikal</TableCell><TableCell>Dobavljači / šifre</TableCell><TableCell>Poslednji put aktivan</TableCell><TableCell>Neaktivan</TableCell><TableCell>Status</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {(candidates.data?.items ?? []).map((row) => <TableRow key={row.identity_key} hover>
            <TableCell padding="checkbox"><Checkbox disabled={!row.export_eligible} checked={selected.includes(row.identity_key)} onChange={() => toggle(row.identity_key)} /></TableCell>
            <TableCell><Typography fontWeight={700}>{row.product_name || "Bez naziva"}</Typography><Typography variant="caption">EAN: {row.ean || "Nedostaje — izvoz nije dozvoljen"}</Typography></TableCell>
            <TableCell>{row.suppliers.map((item) => <Typography variant="body2" key={`${item.supplier_id}-${item.product_code}`}>{item.supplier_name} · {item.product_code}</Typography>)}</TableCell>
            <TableCell>{new Date(row.last_seen_at).toLocaleString("sr-RS")}</TableCell>
            <TableCell>{row.inactive_days} dana</TableCell>
            <TableCell><Chip size="small" color={row.status === "DEACTIVATED" ? "default" : "warning"} label={statusLabels[row.status]} />{row.export_batch_code && <Typography variant="caption" display="block">{row.export_batch_code}</Typography>}</TableCell>
          </TableRow>)}
          {!candidates.isLoading && candidates.data?.items.length === 0 && <TableRow><TableCell colSpan={6}>Nema EOL kandidata za izabrane uslove.</TableCell></TableRow>}
        </TableBody>
      </Table>
    </TableContainer>
    <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)} fullWidth maxWidth="sm">
      <DialogTitle>Priprema deaktivacije</DialogTitle>
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>Biće napravljen audit paket za {selected.length} artikala. Ovaj korak ne menja sajt niti Pantheon dok odgovarajući konektori ne budu povezani.</Alert>
        <FormControlLabel control={<Checkbox checked={website} onChange={(event) => setWebsite(event.target.checked)} />} label="Sajt" />
        <FormControlLabel control={<Checkbox checked={pantheon} onChange={(event) => setPantheon(event.target.checked)} />} label="Pantheon" />
      </DialogContent>
      <DialogActions><Button onClick={() => setConfirmOpen(false)}>Otkaži</Button><Button variant="contained" disabled={(!website && !pantheon) || prepare.isPending} onClick={() => prepare.mutate()}>Potvrdi paket</Button></DialogActions>
    </Dialog>
  </Box>;
}
