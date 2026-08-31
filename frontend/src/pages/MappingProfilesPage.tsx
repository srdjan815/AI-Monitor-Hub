import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  MenuItem,
  Paper,
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
import toast from "react-hot-toast";
import { supplierApi } from "../api/supplierApi";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Operation } from "../types";

const TARGETS = [
  { value: "product_code", label: "Šifra proizvoda", help: "Jedinstvena šifra proizvoda kod dobavljača." },
  { value: "ean", label: "Barkod (EAN)", help: "EAN ili drugi standardni barkod proizvoda." },
  { value: "name", label: "Naziv proizvoda", help: "Puni naziv proizvoda." },
  { value: "description", label: "Opis proizvoda", help: "Tekstualni opis proizvoda." },
  { value: "manufacturer", label: "Proizvođač", help: "Naziv proizvođača ili brenda." },
  { value: "manufacturer_part_number", label: "Šifra proizvođača", help: "Kataloška šifra koju daje proizvođač." },
  { value: "category", label: "Kategorija", help: "Kategorija ili grupa proizvoda dobavljača." },
  { value: "price", label: "Cena", help: "Nabavna ili prodajna cena iz cenovnika." },
  { value: "currency", label: "Valuta", help: "Oznaka valute, na primer RSD ili EUR." },
  { value: "vat_rate", label: "Stopa PDV-a", help: "Procenat poreza na dodatu vrednost." },
  { value: "stock", label: "Količina na stanju", help: "Broj trenutno dostupnih komada." },
  { value: "stock_status", label: "Status dostupnosti", help: "Tekstualna oznaka dostupnosti proizvoda." },
  { value: "image_url", label: "Slika proizvoda", help: "Internet adresa slike proizvoda." },
  { value: "product_url", label: "Stranica proizvoda", help: "Internet adresa proizvoda kod dobavljača." }
];

function suggestedTarget(name: string): string {
  const normalized = name.toLocaleLowerCase("sr-RS").replace(/[^a-z0-9čćžšđ]+/g, "_");
  const suggestions: Array<[RegExp, string]> = [
    [/^(sifra|šifra|sku|code|product_code)$/, "product_code"],
    [/^acproduct$/, "product_code"],
    [/^(barkod|barcode|ean|gtin)$/, "ean"],
    [/^acean$/, "ean"],
    [/^(naziv|name|product_name)$/, "name"],
    [/^acname$/, "name"],
    [/^(opis|description)$/, "description"],
    [/^(acinlinespecification|acproductdescription)$/, "description"],
    [/^(proizvodjac|proizvođač|manufacturer|brand)$/, "manufacturer"],
    [/^acdept$/, "manufacturer"],
    [/^(mpn|manufacturer_part_number|sifra_proizvodjaca)$/, "manufacturer_part_number"],
    [/^(kategorija|category|grupa|nadgrupa)$/, "category"],
    [/^(cena|price|nabavna_cena|veleprodajna_cena)$/, "price"],
    [/^anprice$/, "price"],
    [/^(valuta|currency)$/, "currency"],
    [/^(pdv|vat|vat_rate)$/, "vat_rate"],
    [/^(stanje|stock|kolicina|količina)$/, "stock"],
    [/^anstock$/, "stock"],
    [/^(dostupnost|availability|stock_status)$/, "stock_status"],
    [/^(slika|image|image_url)$/, "image_url"],
    [/^(link|url|product_url)$/, "product_url"],
    [/^acsubcategory$/, "category"]
  ];
  return suggestions.find(([pattern]) => pattern.test(normalized))?.[1] ?? "";
}

function initialSuggestions(fields: AnalysisField[]): Record<string, string> {
  const used = new Set<string>();
  const result: Record<string, string> = {};
  for (const item of fields) {
    const target = suggestedTarget(item.field.name);
    if (target && !used.has(target)) {
      result[item.field.id] = target;
      used.add(target);
    }
  }
  return result;
}

interface AnalysisField {
  field: { id: string; name: string; data_type: string; position: number };
  sample_values: string[];
}

interface StoredAnalysis {
  profile: Operation;
  original_filename?: string | null;
  detected_format: string;
  record_count: number;
  fields: AnalysisField[];
}

interface MappingTestResult {
  successful: boolean;
  tested_records: number;
  warning_count: number;
  error_count: number;
  message: string;
}

interface PriceListRecord {
  record_number: number;
  manufacturer_code?: string | null;
  ean?: string | null;
  name?: string | null;
  price?: string | null;
  values: Record<string, string | null>;
}

function loadAnalysis(): StoredAnalysis | null {
  try {
    const value = localStorage.getItem("amh.schema-analysis");
    return value ? (JSON.parse(value) as StoredAnalysis) : null;
  } catch {
    return null;
  }
}

export function MappingProfilesPage() {
  const workspace = useWorkspace();
  const cache = useQueryClient();
  const [analysis] = useState(loadAnalysis);
  const schemaId = localStorage.getItem("amh.schema-id") ?? "";
  const mappingId = localStorage.getItem("amh.mapping-id") ?? "";
  const [targets, setTargets] = useState<Record<string, string>>(() =>
    initialSuggestions(analysis?.fields ?? [])
  );
  const [testResult, setTestResult] = useState<MappingTestResult | null>(null);
  const [recordSearch, setRecordSearch] = useState("");
  const [appliedRecordSearch, setAppliedRecordSearch] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<PriceListRecord | null>(null);
  const [nameFieldIds, setNameFieldIds] = useState<string[]>([]);
  const [noteFieldIds, setNoteFieldIds] = useState<string[]>([]);
  const root = `/suppliers/${workspace.supplierId}/sources/${workspace.sourceId}/schema-profiles/${schemaId}/mapping-profiles`;
  const recordRoot = root.split("/mapping-profiles")[0];

  const records = useQuery({
    queryKey: ["mapping-record-search", schemaId, appliedRecordSearch],
    queryFn: () =>
      supplierApi.nestedCollection<PriceListRecord>(`${recordRoot}/records`, {
        search: appliedRecordSearch || undefined,
        limit: 20,
        offset: 0
      }),
    enabled: Boolean(appliedRecordSearch)
  });

  const mapping = useQuery({
    queryKey: ["mapping-profile", mappingId],
    queryFn: () => supplierApi.detail<Operation>(`${root}/${mappingId}`),
    enabled: Boolean(workspace.supplierId && workspace.sourceId && schemaId && mappingId)
  });
  const rules = useQuery({
    queryKey: ["mapping-rules", mappingId],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(`${root}/${mappingId}/rules`, {
        active_only: true
      }),
    enabled: Boolean(mappingId)
  });
  const rulesByField = useMemo(
    () =>
      new Map(
        (rules.data?.items ?? []).map((rule) => [
          String(rule.schema_field_id),
          rule
        ])
      ),
    [rules.data]
  );
  const rulesByTarget = useMemo(
    () =>
      new Map(
        (rules.data?.items ?? []).map((rule) => [
          String(rule.target_attribute),
          rule
        ])
      ),
    [rules.data]
  );
  const noteRule = rulesByTarget.get("promotion_note");
  const nameRule = rulesByTarget.get("name");

  useEffect(() => {
    const config = nameRule?.transformation_config as
      | Record<string, unknown>
      | undefined;
    const configured =
      String(nameRule?.transformation_type ?? "") === "CONCAT" &&
      config &&
      Array.isArray(config.field_ids)
        ? config.field_ids.map(String)
        : [];
    setNameFieldIds(configured);
  }, [nameRule]);

  useEffect(() => {
    const config = noteRule?.transformation_config as
      | Record<string, unknown>
      | undefined;
    const configured =
      config && typeof config === "object" && Array.isArray(config.field_ids)
        ? config.field_ids.map(String)
        : noteRule
          ? [String(noteRule.schema_field_id)]
          : [];
    setNoteFieldIds(configured);
  }, [noteRule]);

  const saveRule = useMutation({
    mutationFn: async (field: AnalysisField) => {
      const target = targets[field.field.id];
      const existing = rulesByField.get(field.field.id);
      if (String(existing?.target_attribute ?? "") === target) return;
      const conflicting = target ? rulesByTarget.get(target) : undefined;
      if (
        conflicting &&
        String(conflicting.schema_field_id) !== field.field.id
      ) {
        await supplierApi.mutate(
          `${root}/${mappingId}/rules/${conflicting.id}`,
          "DELETE"
        );
      }
      if (existing) {
        if (!target) {
          await supplierApi.mutate(
            `${root}/${mappingId}/rules/${existing.id}`,
            "DELETE"
          );
          return;
        }
        await supplierApi.mutate(
          `${root}/${mappingId}/rules/${existing.id}`,
          "PATCH",
          {
            optimistic_version: existing.optimistic_version,
            target_attribute: target
          }
        );
        return;
      }
      if (!target) return;
      await supplierApi.mutate(`${root}/${mappingId}/rules`, "POST", {
        schema_field_id: field.field.id,
        target_attribute: target,
        transformation_type: "COPY",
        priority: field.field.position,
        required: target === "product_code"
      });
    },
    onSuccess: () => {
      setTestResult(null);
      toast.success("Polje je mapirano.");
      cache.invalidateQueries({ queryKey: ["mapping-rules", mappingId] });
      cache.invalidateQueries({ queryKey: ["mapping-profile", mappingId] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const saveCombinedNote = useMutation({
    mutationFn: async () => {
      if (!noteFieldIds.length) {
        if (noteRule) {
          await supplierApi.mutate(
            `${root}/${mappingId}/rules/${noteRule.id}`,
            "DELETE"
          );
        }
        return;
      }
      const selectedFields = (analysis?.fields ?? [])
        .filter((item) => noteFieldIds.includes(item.field.id))
        .sort((left, right) => left.field.position - right.field.position);
      const existingAnchor = selectedFields.find(
        (item) => item.field.id === String(noteRule?.schema_field_id ?? "")
      );
      const freeAnchor = selectedFields.find(
        (item) => !rulesByField.has(item.field.id)
      );
      const anchor = existingAnchor ?? freeAnchor;
      if (!anchor) {
        throw {
          status: 409,
          code: "mapping_note_anchor_required",
          message:
            "Najmanje jedno izabrano polje mora biti slobodno za objedinjenu napomenu."
        } satisfies ApiError;
      }
      const transformation_config = {
        field_ids: selectedFields.map((item) => item.field.id),
        labels: Object.fromEntries(
          selectedFields.map((item) => [item.field.id, item.field.name])
        ),
        separator: " | "
      };
      if (noteRule) {
        await supplierApi.mutate(
          `${root}/${mappingId}/rules/${noteRule.id}`,
          "PATCH",
          {
            optimistic_version: noteRule.optimistic_version,
            schema_field_id: anchor.field.id,
            transformation_type: "CONCAT",
            transformation_config
          }
        );
        return;
      }
      await supplierApi.mutate(`${root}/${mappingId}/rules`, "POST", {
        schema_field_id: anchor.field.id,
        target_attribute: "promotion_note",
        transformation_type: "CONCAT",
        transformation_config,
        priority: anchor.field.position,
        required: false
      });
    },
    onSuccess: () => {
      setTestResult(null);
      toast.success("Objedinjena napomena je sačuvana.");
      cache.invalidateQueries({ queryKey: ["mapping-rules", mappingId] });
      cache.invalidateQueries({ queryKey: ["mapping-profile", mappingId] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const saveCompositeName = useMutation({
    mutationFn: async () => {
      if (!nameFieldIds.length) {
        if (nameRule && String(nameRule.transformation_type) === "CONCAT") {
          await supplierApi.mutate(
            `${root}/${mappingId}/rules/${nameRule.id}`,
            "PATCH",
            {
              optimistic_version: nameRule.optimistic_version,
              transformation_type: "COPY",
              transformation_config: null
            }
          );
        }
        return;
      }
      const selectedFields = (analysis?.fields ?? [])
        .filter((item) => nameFieldIds.includes(item.field.id))
        .sort((left, right) => left.field.position - right.field.position);
      const existingAnchor = selectedFields.find(
        (item) => item.field.id === String(nameRule?.schema_field_id ?? "")
      );
      const freeAnchor = selectedFields.find(
        (item) => !rulesByField.has(item.field.id)
      );
      const anchor = existingAnchor ?? (!nameRule ? freeAnchor : undefined);
      if (!anchor) {
        throw {
          status: 409,
          code: "mapping_name_anchor_required",
          message:
            "Izaberite i polje koje je već mapirano kao Naziv proizvoda."
        } satisfies ApiError;
      }
      const transformation_config = {
        field_ids: selectedFields.map((item) => item.field.id),
        labels: {},
        separator: " — ",
        include_labels: false,
        deduplicate: true,
        skip_contained: true
      };
      if (nameRule) {
        await supplierApi.mutate(
          `${root}/${mappingId}/rules/${nameRule.id}`,
          "PATCH",
          {
            optimistic_version: nameRule.optimistic_version,
            schema_field_id: anchor.field.id,
            transformation_type: "CONCAT",
            transformation_config
          }
        );
        return;
      }
      await supplierApi.mutate(`${root}/${mappingId}/rules`, "POST", {
        schema_field_id: anchor.field.id,
        target_attribute: "name",
        transformation_type: "CONCAT",
        transformation_config,
        priority: anchor.field.position,
        required: true
      });
    },
    onSuccess: () => {
      setTestResult(null);
      toast.success("Pravilo za sastavljen naziv je sačuvano.");
      cache.invalidateQueries({ queryKey: ["mapping-rules", mappingId] });
      cache.invalidateQueries({ queryKey: ["mapping-profile", mappingId] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const testMapping = useMutation({
    mutationFn: () =>
      supplierApi.mutate<MappingTestResult>(
        `${root}/${mappingId}/test${selectedRecord ? `?record_number=${selectedRecord.record_number}` : ""}`,
        "POST"
      ),
    onSuccess: (data) => {
      setTestResult(data);
      toast.success(String(data.message));
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const activate = useMutation({
    mutationFn: async () => {
      const result = await supplierApi.mutate<MappingTestResult>(
        `${root}/${mappingId}/test${selectedRecord ? `?record_number=${selectedRecord.record_number}` : ""}`,
        "POST"
      );
      setTestResult(result);
      if (!result.successful) {
        throw {
          status: 409,
          code: "mapping_test_failed",
          message:
            result.message ||
            "Mapiranje sadrži greške i ne može biti aktivirano."
        } satisfies ApiError;
      }
      const schemaRoot = root.split("/mapping-profiles")[0];
      const schema = await supplierApi.detail<Operation>(schemaRoot);
      await supplierApi.mutate(`${schemaRoot}/activate`, "POST", {
        version: schema.version
      });
      const currentMapping = await supplierApi.detail<Operation>(
        `${root}/${mappingId}`
      );
      return supplierApi.mutate(`${root}/${mappingId}/activate`, "POST", {
        optimistic_version: currentMapping.optimistic_version
      });
    },
    onSuccess: () => {
      toast.success("Schema i Mapping su aktivirani.");
      cache.invalidateQueries({ queryKey: ["mapping-profile", mappingId] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  if (!analysis || !schemaId || !mappingId) {
    return (
      <>
        <PageHeader
          title="Mapiranje cenovnika"
          description="Mapiranje se pokreće neposredno posle uspešne analize cenovnika."
        />
        <WorkspaceSelector />
        <Alert severity="info">
          Prvo izaberite Source Connection i pokrenite „Analiziraj cenovnik“.
        </Alert>
      </>
    );
  }

  const editable =
    mapping.isLoading ||
    !mapping.data ||
    String(mapping.data.status) === "DRAFT";
  const successful = testResult?.successful === true;
  const orderedNameFields = nameFieldIds
    .map((id) => analysis.fields.find((item) => item.field.id === id))
    .filter((item): item is AnalysisField => Boolean(item));
  const namePreview = orderedNameFields.reduce<string[]>((parts, item) => {
    const value = String(
      selectedRecord?.values[item.field.name] ?? item.sample_values[0] ?? ""
    ).trim();
    if (!value) return parts;
    const normalized = value.toLocaleLowerCase("sr-RS");
    if (
      parts.some(
        (part) => part.toLocaleLowerCase("sr-RS") === normalized ||
          part.toLocaleLowerCase("sr-RS").includes(normalized)
      )
    ) {
      return parts;
    }
    return [...parts, value];
  }, []).join(" — ");

  return (
    <>
      <PageHeader
        title="Mapiranje cenovnika"
        description="Za svako polje iz cenovnika izaberite šta ono predstavlja u sistemu."
      />
      <WorkspaceSelector />
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} gap={3} alignItems="center">
          <Typography fontWeight={700}>
            {analysis.original_filename ?? "Preuzeti cenovnik"}
          </Typography>
          <Typography>Format: {analysis.detected_format}</Typography>
          <Typography>Proizvoda: {analysis.record_count}</Typography>
          <Typography>Polja: {analysis.fields.length}</Typography>
          <Typography>Schema:</Typography>
          <StatusChip value={String(analysis.profile.status ?? "DRAFT")} />
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Sastavljen naziv proizvoda</Typography>
        <Typography color="text.secondary" mb={1}>
          Opciono spojite više izvornih polja u jedan naziv. Originalne vrednosti
          ostaju sačuvane, prazna i već sadržana polja se ne dodaju ponovo.
        </Typography>
        <TextField
          select
          fullWidth
          label="Polja koja čine naziv"
          value={nameFieldIds}
          disabled={!editable}
          SelectProps={{
            multiple: true,
            renderValue: (selected) =>
              (selected as string[])
                .map(
                  (id) =>
                    analysis.fields.find((item) => item.field.id === id)?.field
                      .name ?? id
                )
                .join(" + ")
          }}
          onChange={(event) => {
            const value = event.target.value;
            setNameFieldIds(
              typeof value === "string"
                ? value.split(",")
                : (value as unknown as string[])
            );
            setTestResult(null);
          }}
        >
          {analysis.fields.map((item) => (
            <MenuItem key={item.field.id} value={item.field.id}>
              <Checkbox checked={nameFieldIds.includes(item.field.id)} />
              {item.field.name}
            </MenuItem>
          ))}
        </TextField>
        {orderedNameFields.length > 0 && (
          <Stack gap={0.75} mt={1.5}>
            {orderedNameFields.map((item, index) => (
              <Stack
                key={item.field.id}
                direction={{ xs: "column", sm: "row" }}
                gap={1}
                alignItems={{ sm: "center" }}
                sx={{ p: 1, border: 1, borderColor: "divider", borderRadius: 1 }}
              >
                <Typography sx={{ flex: 1 }}>
                  {index + 1}. {item.field.name}
                </Typography>
                <Button
                  size="small"
                  disabled={!editable || index === 0}
                  onClick={() =>
                    setNameFieldIds((current) => {
                      const next = [...current];
                      [next[index - 1], next[index]] = [next[index], next[index - 1]];
                      return next;
                    })
                  }
                >
                  Pomeri gore
                </Button>
                <Button
                  size="small"
                  disabled={!editable || index === orderedNameFields.length - 1}
                  onClick={() =>
                    setNameFieldIds((current) => {
                      const next = [...current];
                      [next[index], next[index + 1]] = [next[index + 1], next[index]];
                      return next;
                    })
                  }
                >
                  Pomeri dole
                </Button>
                <Button
                  size="small"
                  color="error"
                  disabled={!editable}
                  onClick={() =>
                    setNameFieldIds((current) =>
                      current.filter((id) => id !== item.field.id)
                    )
                  }
                >
                  Ukloni
                </Button>
              </Stack>
            ))}
          </Stack>
        )}
        {namePreview && (
          <Alert severity="info" sx={{ mt: 1.5 }}>
            Pregled naziva: {namePreview}
          </Alert>
        )}
        <Button
          variant="outlined"
          sx={{ mt: 1 }}
          disabled={!editable || saveCompositeName.isPending}
          onClick={() => saveCompositeName.mutate()}
        >
          Sačuvaj sastavljen naziv
        </Button>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Izaberi artikal za proveru mapiranja</Typography>
        <Typography color="text.secondary" mb={2}>
          Pretražite šifru, EAN, naziv, cenu ili bilo koju vrednost iz izvornog cenovnika.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} gap={1} mb={2}>
          <TextField
            fullWidth
            size="small"
            label="Pretraži artikal"
            value={recordSearch}
            onChange={(event) => setRecordSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") setAppliedRecordSearch(recordSearch.trim());
            }}
          />
          <Button
            variant="outlined"
            disabled={!recordSearch.trim()}
            onClick={() => setAppliedRecordSearch(recordSearch.trim())}
          >
            Pretraži
          </Button>
        </Stack>
        {(records.data?.items ?? []).map((record) => (
          <Button
            key={record.record_number}
            fullWidth
            variant={selectedRecord?.record_number === record.record_number ? "contained" : "text"}
            sx={{ justifyContent: "flex-start", mb: 0.5 }}
            onClick={() => {
              setSelectedRecord(record);
              setTestResult(null);
            }}
          >
            Red {record.record_number} · {record.manufacturer_code || "bez šifre proizvođača"} · {record.ean || "bez EAN-a"} · {record.name || "bez naziva"} · {record.price || "bez cene"}
          </Button>
        ))}
        {selectedRecord && (
          <Alert severity="success" sx={{ mt: 1 }}>
            Test mapiranja koristiće izvorni red {selectedRecord.record_number}: {selectedRecord.name || selectedRecord.manufacturer_code || selectedRecord.ean}.
          </Alert>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Objedinjena napomena dobavljača</Typography>
        <Typography color="text.secondary" mb={1}>
          Izaberite sva opisna polja za akcije, promocije, preporuke i napomene.
          Prazne i negativne vrednosti se preskaču, a ostale se čuvaju u jednoj napomeni.
        </Typography>
        <Stack direction={{ xs: "column", md: "row" }} useFlexGap flexWrap="wrap">
          {analysis.fields.map((item) => (
            <FormControlLabel
              key={item.field.id}
              control={
                <Checkbox
                  checked={noteFieldIds.includes(item.field.id)}
                  disabled={!editable}
                  onChange={(event) => {
                    setNoteFieldIds((current) =>
                      event.target.checked
                        ? [...current, item.field.id]
                        : current.filter((id) => id !== item.field.id)
                    );
                    setTestResult(null);
                  }}
                />
              }
              label={item.field.name}
            />
          ))}
        </Stack>
        <Button
          variant="outlined"
          sx={{ mt: 1 }}
          disabled={!editable || saveCombinedNote.isPending}
          onClick={() => saveCombinedNote.mutate()}
        >
          Sačuvaj objedinjenu napomenu
        </Button>
      </Paper>

      <TableContainer component={Paper} variant="outlined">
        <Typography sx={{ p: 2 }} color="text.secondary">
          Sistem je ponudio početne predloge prema nazivima kolona. Svaki
          predlog možete slobodno promeniti. Proverite primer vrednosti,
          izaberite odgovarajuće značenje i kliknite „Sačuvaj“. Polja koja ne
          želite da koristite ostavite kao „Ne koristi“.
        </Typography>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Pronađeno polje</TableCell>
              <TableCell>Primer vrednosti</TableCell>
              <TableCell>Šta ovo polje predstavlja?</TableCell>
              <TableCell align="right">Akcija</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {analysis.fields.map((item) => {
              const existing = rulesByField.get(item.field.id);
              const selected =
                targets[item.field.id] ?? String(existing?.target_attribute ?? "");
              return (
                <TableRow key={item.field.id}>
                  <TableCell>
                    <Typography fontWeight={650}>{item.field.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.field.data_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {selectedRecord?.values[item.field.name] ??
                      (item.sample_values.slice(0, 3).join(" · ") || "—")}
                  </TableCell>
                  <TableCell sx={{ minWidth: 260 }}>
                    <TextField
                      select
                      fullWidth
                      size="small"
                      value={selected}
                      disabled={!editable}
                      onChange={(event) => {
                        const nextTarget = event.target.value;
                        setTargets((current) => {
                          const updated = { ...current };
                          if (nextTarget) {
                            for (const [fieldId, target] of Object.entries(updated)) {
                              if (fieldId !== item.field.id && target === nextTarget) {
                                updated[fieldId] = "";
                              }
                            }
                          }
                          updated[item.field.id] = nextTarget;
                          return updated;
                        });
                        setTestResult(null);
                      }}
                    >
                      <MenuItem value="">Ne koristi ovo polje</MenuItem>
                      {TARGETS.map((target) => (
                        <MenuItem key={target.value} value={target.value}>
                          {target.label} — {target.help}
                        </MenuItem>
                      ))}
                    </TextField>
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      disabled={
                        !editable ||
                        saveRule.isPending ||
                        !(item.field.id in targets) ||
                        targets[item.field.id] === existing?.target_attribute
                      }
                      onClick={() => saveRule.mutate(item)}
                    >
                      Sačuvaj
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack direction={{ xs: "column", sm: "row" }} gap={1} mt={2}>
        <Button
          variant="outlined"
          disabled={!editable || testMapping.isPending || !rules.data?.total}
          onClick={() => testMapping.mutate()}
        >
          Testiraj mapiranje
        </Button>
        <Button
          variant="contained"
          disabled={
            !editable ||
            !rules.data?.total ||
            testMapping.isPending ||
            activate.isPending
          }
          onClick={() => activate.mutate()}
        >
          Aktiviraj
        </Button>
      </Stack>
      {testResult && (
        <Alert severity={successful ? "success" : "error"} sx={{ mt: 2 }}>
          {String(testResult.message)} Testirano:{" "}
          {String(testResult.tested_records ?? 0)}; greške:{" "}
          {String(testResult.error_count ?? 0)}; upozorenja:{" "}
          {String(testResult.warning_count ?? 0)}.
        </Alert>
      )}
    </>
  );
}
