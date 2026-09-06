import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { srLatn } from "date-fns/locale";
import { DatePicker, LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFnsV3";
import {
  Alert, Button, Dialog, DialogContent, DialogTitle, FormControl, InputLabel,
  MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TablePagination, TableRow, TextField, Typography
} from "@mui/material";
import { api, queryString } from "../api/client";
import { EmptyState, LoadingBlock } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import type {
  ArchivedPriceListItem, ArchivedPriceListItemPage, Page,
  PriceListArchiveEntry, PriceListArchiveFilters
} from "../types";

const pageSize = 50;

const bytes = (value?: number | null) => {
  if (value == null) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount.toLocaleString("sr-RS", { maximumFractionDigits: 2 })} ${units[index]}`;
};

const storageLabels: Record<string, string> = {
  LOCAL: "Lokalno",
  TRANSFER_PENDING: "Čeka prenos",
  NAS_VERIFIED: "NAS verifikovan",
  TRANSFER_FAILED: "Prenos neuspešan"
};

function startOfDay(value: Date | null) {
  return value ? `${format(value, "yyyy-MM-dd")}T00:00:00` : undefined;
}

function endOfDay(value: Date | null) {
  return value ? `${format(value, "yyyy-MM-dd")}T23:59:59.999` : undefined;
}

export function PriceListArchivePage() {
  const [supplierId, setSupplierId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [dateFrom, setDateFrom] = useState<Date | null>(null);
  const [dateTo, setDateTo] = useState<Date | null>(null);
  const [fileSearch, setFileSearch] = useState("");
  const [archiveOffset, setArchiveOffset] = useState(0);
  const [selected, setSelected] = useState<PriceListArchiveEntry | null>(null);
  const [itemSearch, setItemSearch] = useState("");
  const [validationStatus, setValidationStatus] = useState("");
  const [itemOffset, setItemOffset] = useState(0);
  const [details, setDetails] = useState<ArchivedPriceListItem | null>(null);
  const articleSectionRef = useRef<HTMLDivElement | null>(null);

  const filters = useQuery({
    queryKey: ["price-list-archive-filters"],
    queryFn: () => api<PriceListArchiveFilters>("/price-list-archive/filters")
  });
  const sources = useMemo(
    () => (filters.data?.sources ?? []).filter((item) => !supplierId || item.supplier_id === supplierId),
    [filters.data?.sources, supplierId]
  );
  useEffect(() => {
    if (sourceId && !sources.some((item) => item.id === sourceId)) setSourceId("");
  }, [sourceId, sources]);

  const archives = useQuery({
    queryKey: ["price-list-archive", supplierId, sourceId, dateFrom?.getTime(), dateTo?.getTime(), fileSearch, archiveOffset],
    queryFn: () => api<Page<PriceListArchiveEntry>>(`/price-list-archive${queryString({
      supplier_id: supplierId, source_id: sourceId, date_from: startOfDay(dateFrom),
      date_to: endOfDay(dateTo), search: fileSearch.trim(), limit: pageSize, offset: archiveOffset
    })}`)
  });
  const items = useQuery({
    queryKey: ["price-list-archive-items", selected?.acquisition_run_id, itemSearch, validationStatus, itemOffset],
    queryFn: () => api<ArchivedPriceListItemPage>(`/price-list-archive/${selected!.acquisition_run_id}/items${queryString({
      search: itemSearch.trim(), validation_status: validationStatus, limit: pageSize, offset: itemOffset
    })}`),
    enabled: Boolean(selected)
  });

  const resetArchivePage = () => { setArchiveOffset(0); setSelected(null); };
  const chooseArchive = (entry: PriceListArchiveEntry) => {
    setSelected(entry); setItemOffset(0); setItemSearch(""); setValidationStatus("");
  };
  useEffect(() => {
    if (!selected) return;
    window.requestAnimationFrame(() => {
      articleSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [selected]);

  return <>
    <PageHeader title="Arhiva cenovnika" description="Read-only pregled istorijskih cenovnika i artikala. Originalni fajlovi ostaju neizmenjeni i zaštićeni SHA-256 proverom." />
    <Paper sx={{ p: 2, mb: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} gap={1.5} flexWrap="wrap">
        <FormControl sx={{ minWidth: 240 }}><InputLabel>Dobavljač</InputLabel><Select label="Dobavljač" value={supplierId} onChange={(event) => { setSupplierId(event.target.value); resetArchivePage(); }}>{<MenuItem value="">Svi dobavljači</MenuItem>}{(filters.data?.suppliers ?? []).map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</Select></FormControl>
        <FormControl sx={{ minWidth: 240 }}><InputLabel>Izvor</InputLabel><Select label="Izvor" value={sourceId} onChange={(event) => { setSourceId(event.target.value); resetArchivePage(); }}>{<MenuItem value="">Svi izvori</MenuItem>}{sources.map((item) => <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>)}</Select></FormControl>
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={srLatn}>
          <DatePicker label="Od datuma" format="dd.MM.yyyy" value={dateFrom} maxDate={dateTo ?? undefined} onChange={(value) => { setDateFrom(value); resetArchivePage(); }} slotProps={{ textField: { placeholder: "dd.mm.gggg", sx: { width: 180 } } }} />
          <DatePicker label="Do datuma" format="dd.MM.yyyy" value={dateTo} minDate={dateFrom ?? undefined} onChange={(value) => { setDateTo(value); resetArchivePage(); }} slotProps={{ textField: { placeholder: "dd.mm.gggg", sx: { width: 180 } } }} />
        </LocalizationProvider>
        <TextField label="Naziv fajla ili oznaka importa" value={fileSearch} onChange={(event) => { setFileSearch(event.target.value); resetArchivePage(); }} sx={{ flex: "1 1 280px" }} />
      </Stack>
    </Paper>

    <Typography variant="h2" mb={1}>Istorijski cenovnici</Typography>
    {archives.isLoading ? <LoadingBlock /> : archives.error ? <Alert severity="error">Arhivirani cenovnici trenutno nisu dostupni.</Alert> : archives.data?.items.length ? <Paper>
      <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Datum</TableCell><TableCell>Dobavljač / izvor</TableCell><TableCell>Fajl / import</TableCell><TableCell align="right">Artikli</TableCell><TableCell align="right">Veličina</TableCell><TableCell>Skladište</TableCell><TableCell /></TableRow></TableHead><TableBody>
        {archives.data.items.map((entry) => <TableRow key={entry.acquisition_run_id} selected={selected?.acquisition_run_id === entry.acquisition_run_id} hover>
          <TableCell>{new Date(entry.imported_at).toLocaleString("sr-RS")}</TableCell>
          <TableCell><Typography fontWeight={700}>{entry.supplier_name}</Typography><Typography variant="caption" color="text.secondary">{entry.source_name}</Typography></TableCell>
          <TableCell><Typography>{entry.original_filename || "Bez originalnog naziva"}</Typography><Typography variant="caption" fontFamily="monospace">{entry.acquisition_code}</Typography></TableCell>
          <TableCell align="right">{entry.total_records.toLocaleString("sr-RS")}</TableCell><TableCell align="right">{bytes(entry.size_bytes)}</TableCell>
          <TableCell><StatusChip value={storageLabels[entry.storage_status] ?? entry.storage_status} /></TableCell>
          <TableCell><Button type="button" onClick={() => chooseArchive(entry)}>Pregledaj artikle</Button></TableCell>
        </TableRow>)}
      </TableBody></Table></TableContainer>
      <TablePagination component="div" count={archives.data.total} page={Math.floor(archiveOffset / pageSize)} rowsPerPage={pageSize} rowsPerPageOptions={[pageSize]} onPageChange={(_, page) => setArchiveOffset(page * pageSize)} />
    </Paper> : <EmptyState title="Nema cenovnika" description="Promenite filtere ili sačekajte prvi uspešan import." />}

    {selected && <Paper ref={articleSectionRef} sx={{ p: 2, mt: 3, scrollMarginTop: 80 }}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1} mb={2}>
        <div><Typography variant="h2">Artikli — {selected.original_filename || selected.acquisition_code}</Typography><Typography color="text.secondary">{selected.supplier_name} · {selected.source_name} · checksum {selected.checksum_sha256 ? `${selected.checksum_sha256.slice(0, 16)}…` : "nije dostupan"}</Typography></div>
        <Button onClick={() => setSelected(null)}>Zatvori pregled</Button>
      </Stack>
      <Stack direction={{ xs: "column", sm: "row" }} gap={1.5} mb={2}>
        <TextField label="Šifra, EAN ili naziv artikla" value={itemSearch} onChange={(event) => { setItemSearch(event.target.value); setItemOffset(0); }} sx={{ flex: 1 }} />
        <FormControl sx={{ minWidth: 210 }}><InputLabel>Rezultat validacije</InputLabel><Select label="Rezultat validacije" value={validationStatus} onChange={(event) => { setValidationStatus(event.target.value); setItemOffset(0); }}><MenuItem value="">Svi zapisi</MenuItem><MenuItem value="ACCEPTED">Prihvaćeni</MenuItem><MenuItem value="REJECTED">Odbijeni</MenuItem></Select></FormControl>
      </Stack>
      {items.isLoading ? <LoadingBlock /> : items.error ? <Alert severity="error">Artikli izabranog cenovnika trenutno nisu dostupni.</Alert> : items.data?.items.length ? <>
        <TableContainer sx={{ maxHeight: 560 }}><Table size="small" stickyHeader><TableHead><TableRow><TableCell>Red</TableCell><TableCell>Šifra</TableCell><TableCell>EAN</TableCell><TableCell>Naziv</TableCell><TableCell>Kategorija</TableCell><TableCell align="right">Cena</TableCell><TableCell align="right">Stanje</TableCell><TableCell>Status</TableCell></TableRow></TableHead><TableBody>
          {items.data.items.map((item) => <TableRow key={item.id} hover onClick={() => setDetails(item)} sx={{ cursor: "pointer" }}><TableCell>{item.record_number}</TableCell><TableCell>{item.product_code ?? "—"}</TableCell><TableCell>{item.ean ?? "—"}</TableCell><TableCell>{item.name ?? "—"}</TableCell><TableCell>{item.category ?? "—"}</TableCell><TableCell align="right">{item.price ?? "—"} {item.currency ?? ""}</TableCell><TableCell align="right">{item.stock ?? "—"}</TableCell><TableCell><StatusChip value={item.validation_status === "ACCEPTED" ? "Prihvaćen" : "Odbijen"} /></TableCell></TableRow>)}
        </TableBody></Table></TableContainer>
        <TablePagination component="div" count={items.data.total} page={Math.floor(itemOffset / pageSize)} rowsPerPage={pageSize} rowsPerPageOptions={[pageSize]} onPageChange={(_, page) => setItemOffset(page * pageSize)} />
      </> : <EmptyState title="Nema artikala" description="Nijedan zapis ne odgovara izabranim filterima." />}
    </Paper>}

    <Dialog open={Boolean(details)} onClose={() => setDetails(null)} fullWidth maxWidth="md"><DialogTitle>Originalni i mapirani podaci artikla</DialogTitle><DialogContent><Typography variant="h3" mt={1}>Mapirani podaci</Typography><Paper variant="outlined" sx={{ p: 2, my: 1, overflow: "auto" }}><pre>{JSON.stringify(details?.mapped_data ?? {}, null, 2)}</pre></Paper><Typography variant="h3">Originalna polja dobavljača</Typography><Paper variant="outlined" sx={{ p: 2, mt: 1, overflow: "auto" }}><pre>{JSON.stringify(details?.raw_data ?? {}, null, 2)}</pre></Paper></DialogContent></Dialog>
  </>;
}
