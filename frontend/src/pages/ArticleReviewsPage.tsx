import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../state/AuthContext";
import type { ApiError, ArticleReview } from "../types";

const statuses = ["PENDING_REVIEW", "MANUALLY_APPROVED", "REJECTED", "AUTO_RELEASED"];
const issueCodes = [
  "EAN_CHANGED",
  "EAN_SHARED_BY_MULTIPLE_ARTICLES",
  "RECORD_INVALID",
  "ARTICLE_REMOVED",
  "CRITICAL_PRICE_CHANGE",
  "NAME_CHANGED"
];

const statusLabels: Record<string, string> = {
  PENDING_REVIEW: "Čeka pregled",
  MANUALLY_APPROVED: "Ručno odobren",
  REJECTED: "Odbijen",
  AUTO_RELEASED: "Automatski pušten"
};

const issueLabels: Record<string, string> = {
  EAN_CHANGED: "Promenjen EAN za šifru",
  EAN_SHARED_BY_MULTIPLE_ARTICLES: "Više artikala sa istim EAN-om",
  RECORD_INVALID: "Neispravan zapis artikla",
  ARTICLE_REMOVED: "Artikal uklonjen iz cenovnika",
  CRITICAL_PRICE_CHANGE: "Kritična promena cene",
  NAME_CHANGED: "Promenjen naziv artikla",
  MANUAL_REVIEW_REQUIRED: "Potrebna ručna provera"
};

const severityLabels: Record<string, string> = {
  CRITICAL: "Kritično",
  HIGH: "Visoko",
  MEDIUM: "Srednje",
  LOW: "Nisko"
};

export function ArticleReviewsPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [supplierId, setSupplierId] = useState("");
  const [status, setStatus] = useState("PENDING_REVIEW");
  const [issueCode, setIssueCode] = useState("");
  const [productCode, setProductCode] = useState("");
  const [selected, setSelected] = useState<ArticleReview | null>(null);
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [comment, setComment] = useState("");

  const suppliers = useQuery({
    queryKey: ["article-review-suppliers"],
    queryFn: () => supplierApi.suppliers({ limit: 500, offset: 0 })
  });
  const reviews = useQuery({
    queryKey: ["article-reviews", supplierId, status, issueCode, productCode],
    queryFn: () => supplierApi.articleReviews({
      supplier_id: supplierId,
      status,
      issue_code: issueCode,
      product_code: productCode,
      limit: 500,
      offset: 0
    })
  });
  const action = useMutation({
    mutationFn: () => supplierApi.decideArticleReview(
      selected!.id,
      decision!,
      selected!.version,
      comment
    ),
    onSuccess: async (updated) => {
      setSelected(updated);
      setDecision(null);
      setComment("");
      await queryClient.invalidateQueries({ queryKey: ["article-reviews"] });
    }
  });
  const error = reviews.error as ApiError | null;
  const actionError = action.error as ApiError | null;

  const changedFields = useMemo(
    () => selected?.field_changes ?? [],
    [selected]
  );

  return (
    <Box>
      <PageHeader
        title="Centar za kontrolu artikala"
        description="Blokirani artikli ostaju van objave i poslovne statistike dok ih operater ne odobri ili dobavljač ne dostavi ispravku."
      />
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} gap={2}>
          <FormControl size="small" sx={{ minWidth: 220 }}>
            <InputLabel>Dobavljač</InputLabel>
            <Select value={supplierId} label="Dobavljač" onChange={(event) => setSupplierId(event.target.value)}>
              <MenuItem value="">Svi dobavljači</MenuItem>
              {(suppliers.data?.items ?? []).map((supplier) => (
                <MenuItem key={supplier.id} value={supplier.id}>{supplier.company_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 210 }}>
            <InputLabel>Status</InputLabel>
            <Select value={status} label="Status" onChange={(event) => setStatus(event.target.value)}>
              <MenuItem value="">Svi statusi</MenuItem>
              {statuses.map((value) => <MenuItem key={value} value={value}>{statusLabels[value]}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 260 }}>
            <InputLabel>Tip greške</InputLabel>
            <Select value={issueCode} label="Tip greške" onChange={(event) => setIssueCode(event.target.value)}>
              <MenuItem value="">Sve kontrole</MenuItem>
              {issueCodes.map((value) => <MenuItem key={value} value={value}>{issueLabels[value]}</MenuItem>)}
            </Select>
          </FormControl>
          <TextField size="small" label="Šifra artikla" value={productCode} onChange={(event) => setProductCode(event.target.value)} />
        </Stack>
      </Paper>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error.message}</Alert>}
      <TableContainer component={Paper}>
        <Table>
          <TableHead><TableRow>
            <TableCell>Artikal</TableCell><TableCell>Dobavljač / izvor</TableCell><TableCell>Kontrole</TableCell><TableCell>Status</TableCell><TableCell>Otvoreno</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {(reviews.data?.items ?? []).map((row) => (
              <TableRow key={row.id} hover onClick={() => setSelected(row)} sx={{ cursor: "pointer" }}>
                <TableCell><Typography fontWeight={700}>{row.product_code}</Typography><Typography variant="caption">EAN: {row.ean || "—"}</Typography></TableCell>
                <TableCell>{row.supplier_name}<Typography variant="caption" display="block">{row.source_name}</Typography></TableCell>
                <TableCell><Stack direction="row" gap={0.5} flexWrap="wrap">{row.issue_codes.map((code) => <Chip key={code} label={issueLabels[code] ?? code} size="small" color="warning" />)}</Stack></TableCell>
                <TableCell><StatusChip value={row.status} label={statusLabels[row.status]} /></TableCell>
                <TableCell>{new Date(row.opened_at).toLocaleString("sr-RS")}</TableCell>
              </TableRow>
            ))}
            {!reviews.isLoading && reviews.data?.items.length === 0 && <TableRow><TableCell colSpan={5}>Nema artikala za izabrane filtere.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
      <DetailDrawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.product_code ?? "Kontrola artikla"}
        subtitle={selected ? `${selected.supplier_name} · ${selected.source_name} · ${selected.delta_code}` : undefined}
        actions={selected?.status === "PENDING_REVIEW" && auth.can("article_reviews.decide") ? <>
          <Button variant="contained" color="success" onClick={() => setDecision("approve")}>Pusti dalje</Button>
          <Button variant="outlined" color="error" onClick={() => setDecision("reject")}>Odbij</Button>
        </> : undefined}
      >
        {selected && <Stack gap={2}>
          {selected.status === "AUTO_RELEASED" && <Alert severity="success">Dobavljač je dostavio ispravljenu verziju i blokada je automatski uklonjena.</Alert>}
          <Stack direction="row" gap={1}><StatusChip value={selected.status} label={statusLabels[selected.status]} /><StatusChip value={selected.severity} label={severityLabels[selected.severity]} /></Stack>
          {changedFields.map((field, index) => <Paper variant="outlined" sx={{ p: 1.5 }} key={`${String(field.field_path)}-${index}`}>
            <Typography fontWeight={700}>{String(field.field_path)}</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} gap={2} mt={1}>
              <Box flex={1}><Typography variant="caption" color="text.secondary">PRE</Typography><Typography sx={{ overflowWrap: "anywhere" }}>{String(field.previous_value ?? "—")}</Typography></Box>
              <Box flex={1}><Typography variant="caption" color="text.secondary">POSLE</Typography><Typography color="primary" sx={{ overflowWrap: "anywhere" }}>{String(field.current_value ?? "—")}</Typography></Box>
            </Stack>
          </Paper>)}
          {changedFields.length === 0 && <Alert severity="info">Kontrola se odnosi na ceo zapis: uporedite kompletne podatke ispod.</Alert>}
          <Typography variant="h3">Pre</Typography><Paper variant="outlined" sx={{ p: 1.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(selected.previous_data, null, 2)}</Paper>
          <Typography variant="h3">Posle</Typography><Paper variant="outlined" sx={{ p: 1.5, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(selected.current_data, null, 2)}</Paper>
        </Stack>}
      </DetailDrawer>
      <Dialog open={Boolean(decision)} onClose={() => setDecision(null)} fullWidth>
        <DialogTitle>{decision === "approve" ? "Pusti artikal dalje" : "Odbij artikal"}</DialogTitle>
        <DialogContent>
          <Alert severity={decision === "approve" ? "warning" : "info"} sx={{ mb: 2 }}>Odluka se trajno beleži u audit istoriji.</Alert>
          {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError.message}</Alert>}
          <TextField autoFocus fullWidth multiline minRows={3} label="Obrazloženje" value={comment} onChange={(event) => setComment(event.target.value)} />
        </DialogContent>
        <DialogActions><Button onClick={() => setDecision(null)}>Otkaži</Button><Button variant="contained" disabled={comment.trim().length < 3 || action.isPending} onClick={() => action.mutate()}>Potvrdi</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
