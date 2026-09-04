import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { supplierApi } from "../api/supplierApi";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Operation } from "../types";

import { initialSuggestions, loadAnalysis, REQUIRED_TARGETS, TARGETS, type AnalysisField, type MappingTestResult, type PriceListRecord } from "./mapping/mappingConfiguration";
import { CombinedNotePanel, CompositeNamePanel, MappingRecordSelector, MappingRulesTable } from "./mapping/MappingPanels";

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
  const missingRequiredTargets = TARGETS.filter(
    (target) => REQUIRED_TARGETS.has(target.value) && !rulesByTarget.has(target.value)
  );
  const requireCoreMappings = () => {
    if (!missingRequiredTargets.length) return;
    throw {
      status: 409,
      code: "mapping_required_targets_missing",
      message: `Mapirajte obavezna polja: ${missingRequiredTargets
        .map((target) => target.label.replace(" *", ""))
        .join(", ")}.`
    } satisfies ApiError;
  };
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
            target_attribute: target,
            required: REQUIRED_TARGETS.has(target)
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
        required: REQUIRED_TARGETS.has(target)
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
    mutationFn: () => {
      requireCoreMappings();
      return supplierApi.mutate<MappingTestResult>(
        `${root}/${mappingId}/test${selectedRecord ? `?record_number=${selectedRecord.record_number}` : ""}`,
        "POST"
      );
    },
    onSuccess: (data) => {
      setTestResult(data);
      toast.success(String(data.message));
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const activate = useMutation({
    mutationFn: async () => {
      requireCoreMappings();
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

      <CompositeNamePanel fields={analysis.fields} editable={editable} selectedRecord={selectedRecord} fieldIds={nameFieldIds} setFieldIds={setNameFieldIds} saving={saveCompositeName.isPending} onSave={() => saveCompositeName.mutate()} onChanged={() => setTestResult(null)} />

      <MappingRecordSelector records={records.data?.items ?? []} selectedRecord={selectedRecord} search={recordSearch} onSearch={setRecordSearch} onApplySearch={() => setAppliedRecordSearch(recordSearch.trim())} onSelect={(record) => { setSelectedRecord(record); setTestResult(null); }} />

      <CombinedNotePanel fields={analysis.fields} editable={editable} fieldIds={noteFieldIds} setFieldIds={setNoteFieldIds} saving={saveCombinedNote.isPending} onSave={() => saveCombinedNote.mutate()} onChanged={() => setTestResult(null)} />

      <MappingRulesTable fields={analysis.fields} selectedRecord={selectedRecord} rulesByField={rulesByField} targets={targets} setTargets={setTargets} editable={editable} saving={saveRule.isPending} onSave={(field) => saveRule.mutate(field)} onChanged={() => setTestResult(null)} />

      {missingRequiredTargets.length > 0 && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          Pre testiranja i aktivacije mapirajte obavezna polja: {missingRequiredTargets
            .map((target) => target.label.replace(" *", ""))
            .join(", ")}.
        </Alert>
      )}

      <Stack direction={{ xs: "column", sm: "row" }} gap={1} mt={2}>
        <Button
          variant="outlined"
          disabled={
            !editable ||
            testMapping.isPending ||
            !rules.data?.total ||
            missingRequiredTargets.length > 0
          }
          onClick={() => testMapping.mutate()}
        >
          Testiraj mapiranje
        </Button>
        <Button
          variant="contained"
          disabled={
            !editable ||
            !rules.data?.total ||
            missingRequiredTargets.length > 0 ||
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
