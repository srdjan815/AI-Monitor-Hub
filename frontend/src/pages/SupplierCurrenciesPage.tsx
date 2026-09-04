import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
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
  Typography,
} from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import type {
  ApiError,
  CurrencySourceTestResult,
  SupplierCurrencySetting,
} from "../types";

const statusLabels = {
  CURRENT: "Ispravno",
  STALE: "Kurs je zastareo",
  MISSING: "Nedostaje kurs",
} as const;
const modeLabels = {
  FIXED: "Fiksni",
  MANUAL: "Ručni unos",
  AUTOMATIC: "Automatski",
} as const;
const sourceLabels = {
  CONFIGURED: "Valuta iz podešavanja",
  PRICE_LIST: "Valuta iz cenovnika",
} as const;
type ExtractionMethod =
  | "JSON_PATH"
  | "CSS_SELECTOR"
  | "XPATH"
  | "REGEX"
  | "TEXT_LABEL";

export function SupplierCurrenciesPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<SupplierCurrencySetting | null>(
    null,
  );
  const [settingOpen, setSettingOpen] = useState(false);
  const [rateOpen, setRateOpen] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [currency, setCurrency] = useState("RSD");
  const [currencySource, setCurrencySource] = useState<
    "CONFIGURED" | "PRICE_LIST"
  >("CONFIGURED");
  const [rateMode, setRateMode] = useState<"FIXED" | "MANUAL" | "AUTOMATIC">(
    "FIXED",
  );
  const [automaticUrl, setAutomaticUrl] = useState("");
  const [extractionMethod, setExtractionMethod] =
    useState<ExtractionMethod>("TEXT_LABEL");
  const [extractionExpression, setExtractionExpression] = useState("");
  const [fallbackMethod, setFallbackMethod] = useState<ExtractionMethod | "">(
    "",
  );
  const [fallbackExpression, setFallbackExpression] = useState("");
  const [decimalSeparator, setDecimalSeparator] = useState<"." | ",">(".");
  const [dailyCheckTime, setDailyCheckTime] = useState("06:00");
  const [testResult, setTestResult] = useState<CurrencySourceTestResult | null>(
    null,
  );
  const [rate, setRate] = useState("");
  const [note, setNote] = useState("");
  const settings = useQuery({
    queryKey: ["supplier-currencies"],
    queryFn: supplierApi.currencySettings,
  });
  const monitor = useQuery({
    queryKey: ["monitor-currency"],
    queryFn: supplierApi.monitorCurrency,
  });
  const suppliers = useQuery({
    queryKey: ["currency-suppliers"],
    queryFn: () => supplierApi.suppliers({ limit: 500, offset: 0 }),
  });
  const sources = useQuery({
    queryKey: ["currency-sources", supplierId],
    queryFn: () =>
      supplierApi.sources(supplierId, {
        active_only: true,
        status: "ACTIVE",
        limit: 500,
        offset: 0,
      }),
    enabled: Boolean(supplierId),
  });
  useEffect(() => {
    const available = sources.data?.items ?? [];
    if (
      currency !== "RSD" &&
      available.length > 0 &&
      !available.some((item) => item.id === sourceId)
    ) {
      setSourceId(available[0].id);
      setTestResult(null);
    }
  }, [currency, sourceId, sources.data]);
  const selectedSource = (sources.data?.items ?? []).find(
    (item) => item.id === sourceId,
  );
  const rates = useQuery({
    queryKey: ["supplier-exchange-rates", selected?.supplier_id],
    queryFn: () => supplierApi.exchangeRates(selected!.supplier_id),
    enabled: Boolean(selected),
  });
  const configured = useMemo(
    () => new Set((settings.data?.items ?? []).map((item) => item.supplier_id)),
    [settings.data],
  );
  const sourcePayload = {
    source_connection_id: sourceId,
    source_url: automaticUrl,
    extraction_method: extractionMethod,
    extraction_expression: extractionExpression,
    fallback_extraction_method: fallbackMethod || null,
    fallback_extraction_expression: fallbackMethod ? fallbackExpression : null,
    decimal_separator: decimalSeparator,
  };
  const saveSetting = useMutation({
    mutationFn: () =>
      supplierApi.saveCurrencySetting(supplierId, {
        source_connection_id: currency === "RSD" ? null : sourceId,
        currency_code: currency,
        currency_source: currencySource,
        rate_mode: rateMode,
        automatic_source_url: rateMode === "AUTOMATIC" ? automaticUrl : null,
        extraction_method: extractionMethod,
        extraction_expression:
          rateMode === "AUTOMATIC" ? extractionExpression : null,
        fallback_extraction_method:
          rateMode === "AUTOMATIC" && fallbackMethod ? fallbackMethod : null,
        fallback_extraction_expression:
          rateMode === "AUTOMATIC" && fallbackMethod
            ? fallbackExpression
            : null,
        decimal_separator: decimalSeparator,
        daily_check_time: `${dailyCheckTime}:00`,
        max_rate_age_hours: 48,
        expected_version:
          selected?.supplier_id === supplierId ? selected.version : null,
      }),
    onSuccess: async () => {
      setSettingOpen(false);
      setSelected(null);
      await queryClient.invalidateQueries({
        queryKey: ["supplier-currencies"],
      });
    },
  });
  const testSource = useMutation({
    mutationFn: () => supplierApi.testCurrencySource(supplierId, sourcePayload),
    onSuccess: setTestResult,
  });
  const saveRate = useMutation({
    mutationFn: () =>
      supplierApi.addExchangeRate(selected!.supplier_id, {
        rate_to_rsd: rate,
        effective_at: new Date().toISOString(),
        source_type: selected!.rate_mode,
        note,
      }),
    onSuccess: async () => {
      setRateOpen(false);
      setRate("");
      setNote("");
      await queryClient.invalidateQueries({
        queryKey: ["supplier-currencies"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["supplier-exchange-rates"],
      });
    },
  });
  const openNew = () => {
    setSelected(null);
    setSupplierId("");
    setSourceId("");
    setCurrency("RSD");
    setCurrencySource("CONFIGURED");
    setRateMode("FIXED");
    setAutomaticUrl("");
    setExtractionMethod("TEXT_LABEL");
    setExtractionExpression("");
    setFallbackMethod("");
    setFallbackExpression("");
    setDecimalSeparator(".");
    setDailyCheckTime("06:00");
    setTestResult(null);
    setSettingOpen(true);
  };
  const openEdit = (row: SupplierCurrencySetting) => {
    setSelected(row);
    setSupplierId(row.supplier_id);
    setSourceId(row.source_connection_id ?? "");
    setCurrency(row.currency_code);
    setCurrencySource(row.currency_source);
    setRateMode(row.rate_mode);
    setAutomaticUrl(row.automatic_source_url ?? "");
    setExtractionMethod(row.extraction_method);
    setExtractionExpression(row.extraction_expression ?? "");
    setFallbackMethod(row.fallback_extraction_method ?? "");
    setFallbackExpression(row.fallback_extraction_expression ?? "");
    setDecimalSeparator(row.decimal_separator);
    setDailyCheckTime(row.daily_check_time.slice(0, 5));
    setTestResult(null);
    setSettingOpen(true);
  };
  const error = (settings.error ||
    saveSetting.error ||
    saveRate.error ||
    testSource.error) as ApiError | null;
  return (
    <Box>
      <PageHeader
        title="Valute dobavljača"
        description="Osnovna valuta Monitora je RSD sa kursom 1. Dobavljačke cene se zaključavaju uz kurs korišćen za konkretan cenovnik."
        actions={
          <Button variant="contained" onClick={openNew}>
            Dodaj podešavanje
          </Button>
        }
      />
      <Stack direction={{ xs: "column", sm: "row" }} gap={2} mb={2}>
        <Paper sx={{ p: 2, minWidth: 220 }}>
          <Typography color="text.secondary">Monitor valuta</Typography>
          <Typography variant="h2">
            {monitor.data?.currency_code ?? "RSD"} ={" "}
            {monitor.data?.rate_to_rsd ?? "1"}
          </Typography>
        </Paper>
        <Paper sx={{ p: 2, minWidth: 220 }}>
          <Typography color="text.secondary">Podešeni dobavljači</Typography>
          <Typography variant="h2">{settings.data?.total ?? 0}</Typography>
        </Paper>
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error.message}
        </Alert>
      )}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Dobavljač</TableCell>
              <TableCell>Valuta</TableCell>
              <TableCell align="right">Kurs u RSD</TableCell>
              <TableCell>Važi od</TableCell>
              <TableCell>Način</TableCell>
              <TableCell>Status</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {(settings.data?.items ?? []).map((row) => (
              <TableRow
                key={row.id}
                hover
                selected={selected?.id === row.id}
                onClick={() => setSelected(row)}
                sx={{ cursor: "pointer" }}
              >
                <TableCell>{row.supplier_name}</TableCell>
                <TableCell>{row.currency_code}</TableCell>
                <TableCell align="right">{row.current_rate ?? "—"}</TableCell>
                <TableCell>
                  {row.current_rate_effective_at
                    ? new Date(row.current_rate_effective_at).toLocaleString(
                        "sr-RS",
                      )
                    : "—"}
                </TableCell>
                <TableCell>{modeLabels[row.rate_mode]}</TableCell>
                <TableCell>
                  <StatusChip
                    value={row.rate_status}
                    label={statusLabels[row.rate_status]}
                  />
                </TableCell>
                <TableCell>
                  <Button
                    onClick={(event) => {
                      event.stopPropagation();
                      openEdit(row);
                    }}
                  >
                    Izmeni
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {!settings.isLoading && settings.data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7}>
                  Nijedan dobavljač još nema podešenu valutu.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {selected && (
        <Paper sx={{ p: 2, mt: 2 }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            justifyContent="space-between"
            gap={2}
          >
            <Box>
              <Typography variant="h3">
                {selected.supplier_name} — istorija kursa
              </Typography>
              <Typography color="text.secondary">
                {sourceLabels[selected.currency_source]}
              </Typography>
            </Box>
            {selected.currency_code !== "RSD" &&
              selected.rate_mode !== "AUTOMATIC" && (
                <Button variant="contained" onClick={() => setRateOpen(true)}>
                  Dodaj kurs
                </Button>
              )}
          </Stack>
          {selected.rate_mode === "AUTOMATIC" && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Automatski kurs upisuje isključivo interni servis uz dokaz o
              preuzetom izvoru.
            </Alert>
          )}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Datum važenja</TableCell>
                <TableCell align="right">Kurs</TableCell>
                <TableCell>Izvor</TableCell>
                <TableCell>Napomena</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(rates.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    {new Date(item.effective_at).toLocaleString("sr-RS")}
                  </TableCell>
                  <TableCell align="right">{item.rate_to_rsd}</TableCell>
                  <TableCell>
                    {modeLabels[item.source_type as keyof typeof modeLabels] ??
                      item.source_type}
                  </TableCell>
                  <TableCell>{item.note ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Paper>
      )}
      <Dialog
        open={settingOpen}
        onClose={() => setSettingOpen(false)}
        fullWidth
      >
        <DialogTitle>Podešavanje valute dobavljača</DialogTitle>
        <DialogContent>
          <Stack gap={2} mt={1}>
            <FormControl>
              <InputLabel>Dobavljač</InputLabel>
              <Select
                value={supplierId}
                label="Dobavljač"
                disabled={Boolean(selected)}
                onChange={(e) => {
                  setSupplierId(e.target.value);
                  setSourceId("");
                  setTestResult(null);
                }}
              >
                {(suppliers.data?.items ?? [])
                  .filter(
                    (s) =>
                      selected?.supplier_id === s.id || !configured.has(s.id),
                  )
                  .map((s) => (
                    <MenuItem key={s.id} value={s.id}>
                      {s.company_name}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
            {currency !== "RSD" && (
              <>
                <FormControl>
                  <InputLabel>Konekcija cenovnika</InputLabel>
                  <Select
                    value={sourceId}
                    label="Konekcija cenovnika"
                    onChange={(e) => {
                      setSourceId(e.target.value);
                      setTestResult(null);
                    }}
                  >
                    {(sources.data?.items ?? []).map((source) => (
                      <MenuItem key={source.id} value={source.id}>
                        {source.name} ({source.source_code})
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Alert
                  severity={
                    selectedSource?.portal_supplier_code ? "info" : "warning"
                  }
                >
                  Šifra dobavljača na portalu:{" "}
                  {selectedSource?.portal_supplier_code ??
                    "nije podešena na izabranoj konekciji"}
                </Alert>
              </>
            )}
            <TextField
              select
              label="Valuta"
              value={currency}
              onChange={(e) => {
                const value = e.target.value;
                setCurrency(value);
                setRateMode(value === "RSD" ? "FIXED" : "MANUAL");
                if (value === "RSD") setSourceId("");
                setTestResult(null);
              }}
            >
              {[
                "RSD",
                "EUR",
                "USD",
                "HUF",
                "CHF",
                "GBP",
                "BAM",
                "MKD",
                "RON",
                "BGN",
                "CZK",
                "PLN",
                "CNY",
                "JPY",
              ].map((value) => (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              ))}
            </TextField>
            <FormControl>
              <InputLabel>Odakle dolazi valuta</InputLabel>
              <Select
                value={currencySource}
                label="Odakle dolazi valuta"
                onChange={(e) =>
                  setCurrencySource(e.target.value as typeof currencySource)
                }
              >
                <MenuItem value="CONFIGURED">Iz podešavanja</MenuItem>
                <MenuItem value="PRICE_LIST">Obavezna u cenovniku</MenuItem>
              </Select>
            </FormControl>
            {currency === "RSD" ? (
              <Alert severity="info">
                RSD je osnovna valuta i njen kurs je uvek 1.
              </Alert>
            ) : (
              <FormControl>
                <InputLabel>Način kursa</InputLabel>
                <Select
                  value={rateMode}
                  label="Način kursa"
                  onChange={(e) => {
                    setRateMode(e.target.value as typeof rateMode);
                    setTestResult(null);
                  }}
                >
                  <MenuItem value="MANUAL">Ručni unos</MenuItem>
                  <MenuItem value="AUTOMATIC">
                    Automatski sa sajta dobavljača
                  </MenuItem>
                </Select>
              </FormControl>
            )}
            {rateMode === "AUTOMATIC" && currency !== "RSD" && (
              <>
                <TextField
                  label="HTTPS adresa izvora kursa"
                  value={automaticUrl}
                  onChange={(e) => {
                    setAutomaticUrl(e.target.value);
                    setTestResult(null);
                  }}
                />
                <FormControl>
                  <InputLabel>Način pronalaženja vrednosti</InputLabel>
                  <Select
                    value={extractionMethod}
                    label="Način pronalaženja vrednosti"
                    onChange={(e) => {
                      setExtractionMethod(
                        e.target.value as typeof extractionMethod,
                      );
                      setTestResult(null);
                    }}
                  >
                    <MenuItem value="JSON_PATH">JSON putanja</MenuItem>
                    <MenuItem value="CSS_SELECTOR">CSS selektor</MenuItem>
                    <MenuItem value="XPATH">XPath</MenuItem>
                    <MenuItem value="REGEX">Regularni izraz</MenuItem>
                    <MenuItem value="TEXT_LABEL">Tekstualna oznaka</MenuItem>
                  </Select>
                </FormControl>
                <TextField
                  label="Izraz za pronalaženje kursa"
                  helperText={
                    extractionMethod === "JSON_PATH"
                      ? "Primer: $.exchangeRate.value"
                      : extractionMethod === "TEXT_LABEL"
                        ? "Unesite tačan naziv, na primer: Kurs avans"
                        : "Vrednost mora jednoznačno pronaći kurs"
                  }
                  value={extractionExpression}
                  onChange={(e) => {
                    setExtractionExpression(e.target.value);
                    setTestResult(null);
                  }}
                />
                <FormControl>
                  <InputLabel>Rezervni način (opciono)</InputLabel>
                  <Select
                    value={fallbackMethod}
                    label="Rezervni način (opciono)"
                    onChange={(e) => {
                      setFallbackMethod(
                        e.target.value as ExtractionMethod | "",
                      );
                      setFallbackExpression("");
                      setTestResult(null);
                    }}
                  >
                    <MenuItem value="">Bez rezervnog pravila</MenuItem>
                    <MenuItem value="JSON_PATH">JSON putanja</MenuItem>
                    <MenuItem value="CSS_SELECTOR">CSS selektor</MenuItem>
                    <MenuItem value="XPATH">XPath</MenuItem>
                    <MenuItem value="REGEX">Regularni izraz</MenuItem>
                    <MenuItem value="TEXT_LABEL">Tekstualna oznaka</MenuItem>
                  </Select>
                </FormControl>
                {fallbackMethod && (
                  <TextField
                    label="Rezervni izraz ili oznaka"
                    helperText="Koristi se samo ako primarno pravilo ne pronađe vrednost."
                    value={fallbackExpression}
                    onChange={(e) => {
                      setFallbackExpression(e.target.value);
                      setTestResult(null);
                    }}
                  />
                )}
                <Stack direction="row" gap={2}>
                  <TextField
                    select
                    fullWidth
                    label="Decimalni separator"
                    value={decimalSeparator}
                    onChange={(e) =>
                      setDecimalSeparator(
                        e.target.value as typeof decimalSeparator,
                      )
                    }
                  >
                    <MenuItem value=".">Tačka (123.45)</MenuItem>
                    <MenuItem value=",">Zarez (123,45)</MenuItem>
                  </TextField>
                  <TextField
                    fullWidth
                    type="time"
                    label="Dnevna provera"
                    InputLabelProps={{ shrink: true }}
                    value={dailyCheckTime}
                    onChange={(e) => setDailyCheckTime(e.target.value)}
                  />
                </Stack>
                <Button
                  variant="outlined"
                  disabled={
                    !supplierId ||
                    !sourceId ||
                    !automaticUrl ||
                    !extractionExpression ||
                    (Boolean(fallbackMethod) && !fallbackExpression) ||
                    testSource.isPending
                  }
                  onClick={() => testSource.mutate()}
                >
                  Testiraj čitanje
                </Button>
                {testResult && (
                  <Alert severity="success">
                    Pročitan kurs: {testResult.rate_to_rsd} RSD. Metoda:{" "}
                    {testResult.extraction_method_used}. Izvor: „
                    {testResult.source_excerpt}“
                    {testResult.difference_percent != null
                      ? `; promena ${testResult.difference_percent}%`
                      : ""}
                  </Alert>
                )}
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingOpen(false)}>Otkaži</Button>
          <Button
            variant="contained"
            disabled={
              !supplierId ||
              currency.length !== 3 ||
              saveSetting.isPending ||
              (currency !== "RSD" && !sourceId) ||
              (rateMode === "AUTOMATIC" &&
                (!automaticUrl ||
                  !extractionExpression ||
                  !testResult ||
                  (Boolean(fallbackMethod) && !fallbackExpression)))
            }
            onClick={() => saveSetting.mutate()}
          >
            Sačuvaj
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={rateOpen} onClose={() => setRateOpen(false)} fullWidth>
        <DialogTitle>Dodaj kurs za {selected?.supplier_name}</DialogTitle>
        <DialogContent>
          <Stack gap={2} mt={1}>
            <TextField
              label="Kurs prema RSD"
              value={rate}
              onChange={(e) => setRate(e.target.value.replace(",", "."))}
            />
            <TextField
              label="Obrazloženje / izvor"
              multiline
              minRows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRateOpen(false)}>Otkaži</Button>
          <Button
            variant="contained"
            disabled={!rate || note.trim().length < 3 || saveRate.isPending}
            onClick={() => saveRate.mutate()}
          >
            Sačuvaj kurs
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
