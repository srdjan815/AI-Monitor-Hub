import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddRounded,
  ArchiveRounded,
  CheckCircleRounded,
  CloudDownloadRounded,
  KeyRounded,
  LinkRounded,
  ScheduleRounded,
} from "@mui/icons-material";
import { Alert, Button, FormControlLabel, Paper, Stack, Switch, Tooltip, Typography } from "@mui/material";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useAuth } from "../state/AuthContext";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Operation, Source, SourceProbeResult } from "../types";

import { DetailRow, DetailSection } from "./sources/SourceDetails";
import { SourceCredentialsDialog } from "./sources/SourceCredentialsDialog";
import { SourceWizardDialog } from "./sources/SourceWizardDialog";
import { detailValue, displayFormat, displayMethod, formatDate } from "./sources/sourceDisplay";
import { initialForm, isCertificateReady, isPortalReady, sourcePayload, withAuthenticationType, withIntegrationProfile, withSoapProfile, type ConnectionForm } from "./sources/sourceForm";

export function SourcesPage() {
  const workspace = useWorkspace();
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [opened, setOpened] = useState<Source | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(initialForm);
  const [draft, setDraft] = useState<Source | null>(null);
  const [probe, setProbe] = useState<SourceProbeResult | null>(null);
  const [probeSourceId, setProbeSourceId] = useState<string | null>(null);
  const [probeFile, setProbeFile] = useState<File | null>(null);
  const [certificateFile, setCertificateFile] = useState<File | null>(null);
  const [credentialsOpen, setCredentialsOpen] = useState(false);

  useEffect(() => {
    setPage(0);
    setSelected([]);
    setOpened(null);
  }, [workspace.supplierId]);

  const suppliers = useQuery({
    queryKey: ["workspace-suppliers"],
    queryFn: () =>
      supplierApi.suppliers({
        limit: 500,
        offset: 0,
        active_only: true,
      }),
  });
  const supplierNames = useMemo(
    () =>
      new Map(
        (suppliers.data?.items ?? []).map((supplier) => [
          supplier.id,
          `${supplier.supplier_code} · ${supplier.company_name}`,
        ]),
      ),
    [suppliers.data?.items],
  );
  const sources = useQuery({
    queryKey: [
      "sources",
      workspace.supplierId || "all-ready",
      page,
      showArchived,
      suppliers.data?.items.map((supplier) => supplier.id).join(","),
    ],
    queryFn: async () => {
      if (workspace.supplierId) {
        return supplierApi.sources(workspace.supplierId, {
          limit: 25,
          offset: page * 25,
          active_only: !showArchived,
        });
      }
      const pages = await Promise.all(
        (suppliers.data?.items ?? []).map((supplier) =>
          supplierApi.sources(supplier.id, {
            limit: 500,
            offset: 0,
            active_only: true,
            status: "ACTIVE",
          }),
        ),
      );
      const ready = pages
        .flatMap((result) => result.items)
        .filter(
          (source) =>
            source.is_active &&
            source.status === "ACTIVE" &&
            source.last_validation_status === "VALID",
        )
        .sort((left, right) => left.name.localeCompare(right.name, "sr"));
      return {
        items: ready.slice(page * 25, page * 25 + 25),
        total: ready.length,
      };
    },
    enabled: Boolean(workspace.supplierId || suppliers.data),
    placeholderData: (previous) => previous,
  });
  const sourceRoot = opened
    ? `/suppliers/${opened.supplier_id}/sources/${opened.id}`
    : "";
  const sourceSchedule = useQuery({
    queryKey: ["source-details", "schedule", opened?.id],
    queryFn: () => supplierApi.schedule(opened!.supplier_id, opened!.id),
    enabled: Boolean(opened),
  });
  const schemas = useQuery({
    queryKey: ["source-details", "schemas", opened?.id],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(`${sourceRoot}/schema-profiles`, {
        limit: 100,
        offset: 0,
      }),
    enabled: Boolean(opened),
  });
  const schema =
    schemas.data?.items.find((item) => item.status === "ACTIVE") ??
    schemas.data?.items[0];
  const mappings = useQuery({
    queryKey: ["source-details", "mappings", opened?.id, schema?.id],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `${sourceRoot}/schema-profiles/${schema?.id}/mapping-profiles`,
        { limit: 100, offset: 0 },
      ),
    enabled: Boolean(opened && schema),
  });
  const mapping =
    mappings.data?.items.find((item) => item.status === "ACTIVE") ??
    mappings.data?.items[0];
  const acquisitions = useQuery({
    queryKey: ["source-details", "acquisitions", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "acquisitions",
        { limit: 1, offset: 0 },
      ),
    enabled: Boolean(opened),
  });
  const snapshots = useQuery({
    queryKey: ["source-details", "snapshots", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "snapshots",
        { limit: 1, offset: 0 },
      ),
    enabled: Boolean(opened),
  });
  const deltas = useQuery({
    queryKey: ["source-details", "deltas", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "deltas",
        { limit: 1, offset: 0 },
      ),
    enabled: Boolean(opened),
  });
  const acquisition = acquisitions.data?.items[0];
  const snapshot = snapshots.data?.items[0];
  const delta = deltas.data?.items[0];
  const openedProbe = opened?.id === probeSourceId ? probe : null;

  const saveDraft = useMutation({
    mutationFn: async () => {
      const isNewSource = !draft;
      const source = draft
        ? await supplierApi.updateSource(workspace.supplierId, draft.id, {
            ...sourcePayload(form),
            source_type: undefined,
            version: draft.version,
          })
        : await supplierApi.createSource(
            workspace.supplierId,
            sourcePayload(form),
          );
      // Creation and credential storage are separate API operations. Remember
      // the created source before writing secrets so a credential failure can
      // be retried against the same source instead of attempting a duplicate.
      if (isNewSource) {
        setDraft(source);
        setOpened(source);
        workspace.setSourceId(source.id);
        queryClient.invalidateQueries({ queryKey: ["sources"] });
      }
      const hasCredential =
        form.password || form.token || form.api_key || form.imap_password;
      if (hasCredential) {
        await supplierApi.writeSourceCredentials(
          workspace.supplierId,
          source.id,
          {
            placement:
              form.method === "PORTAL"
                ? "PORTAL_FORM"
                : form.integration_profile === "ASBIS_IT4PROFIT"
                  ? "QUERY"
                  : form.integration_profile === "CT_SOAP"
                    ? "SOAP_BODY"
                    : form.placement,
            username: form.username || null,
            password: form.password || null,
            token: form.token || null,
            api_key: form.api_key || null,
            imap_username:
              form.integration_profile === "ASBIS_IT4PROFIT"
                ? form.imap_username || null
                : null,
            imap_password:
              form.integration_profile === "ASBIS_IT4PROFIT"
                ? form.imap_password || null
                : null,
            username_parameter:
              form.integration_profile === "ASBIS_IT4PROFIT"
                ? "USERNAME"
                : form.username_parameter,
            password_parameter:
              form.integration_profile === "ASBIS_IT4PROFIT"
                ? "PASSWORD"
                : form.password_parameter,
            api_key_parameter: form.api_key_parameter,
          },
        );
        return supplierApi.source(workspace.supplierId, source.id);
      }
      if (
        form.authentication_type === "CLIENT_CERTIFICATE" &&
        certificateFile
      ) {
        await supplierApi.writeSourceCertificate(
          workspace.supplierId,
          source.id,
          certificateFile,
          form.certificate_password,
        );
        return supplierApi.source(workspace.supplierId, source.id);
      }
      return source;
    },
    onSuccess: (source) => {
      setDraft(source);
      setOpened(source);
      workspace.setSourceId(source.id);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message),
  });

  const testConnection = useMutation({
    mutationFn: async () => {
      const source = await saveDraft.mutateAsync();
      const result =
        form.method === "MANUAL_UPLOAD" && probeFile
          ? await supplierApi.probeUploadedSource(
              workspace.supplierId,
              source.id,
              probeFile,
            )
          : await supplierApi.probeSource(workspace.supplierId, source.id);
      const refreshed = await supplierApi.source(
        workspace.supplierId,
        source.id,
      );
      return { result, refreshed };
    },
    onSuccess: ({ result, refreshed }) => {
      setDraft(refreshed);
      setProbe(result);
      setProbeSourceId(refreshed.id);
      setStep(2);
      if (result.successful)
        toast.success("Cenovnik je uspešno probno preuzet.");
      else toast.error(result.message);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message),
  });

  const activate = useMutation({
    mutationFn: async (source: Source) =>
      supplierApi.updateSource(source.supplier_id, source.id, {
        version: source.version,
        status: "ACTIVE",
      }),
    onSuccess: (source) => {
      toast.success("Konekcija je aktivirana.");
      setDraft(source);
      setOpened(source);
      setStep(3);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message),
  });

  const archive = useMutation({
    mutationFn: (source: Source) =>
      supplierApi.deactivateSource(source.supplier_id, source.id),
    onSuccess: () => {
      toast.success("Konekcija je arhivirana.");
      setOpened(null);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message),
  });
  const archiveSelected = useMutation({
    mutationFn: async () => {
      const rows = (sources.data?.items ?? []).filter(
        (source) => selected.includes(source.id) && source.is_active,
      );
      const results = await Promise.allSettled(
        rows.map((source) =>
          supplierApi.deactivateSource(source.supplier_id, source.id),
        ),
      );
      return {
        archived: results.filter((result) => result.status === "fulfilled")
          .length,
        failed: results.filter((result) => result.status === "rejected").length,
      };
    },
    onSuccess: ({ archived, failed }) => {
      if (archived) toast.success(`${archived} konekcija je arhivirano.`);
      if (failed) toast.error(`${failed} konekcija nije moguće arhivirati.`);
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });
  const changeCredentials = useMutation({
    mutationFn: async () => {
      if (!opened) throw new Error("Konekcija nije izabrana");
      if (form.authentication_type === "CLIENT_CERTIFICATE") {
        if (!certificateFile || !form.certificate_password) {
          throw new Error("Izaberite sertifikat i unesite njegovu lozinku");
        }
        return supplierApi.writeSourceCertificate(
          opened.supplier_id,
          opened.id,
          certificateFile,
          form.certificate_password,
        );
      }
      return supplierApi.writeSourceCredentials(opened.supplier_id, opened.id, {
        placement:
          form.integration_profile === "ASBIS_IT4PROFIT"
            ? "QUERY"
            : ["CT_SOAP", "PIN_SOAP"].includes(form.integration_profile)
              ? "SOAP_BODY"
              : form.placement,
        username: form.username || null,
        password: form.password || null,
        token: form.token || null,
        api_key: form.api_key || null,
        imap_username:
          form.integration_profile === "ASBIS_IT4PROFIT"
            ? form.imap_username || null
            : null,
        imap_password:
          form.integration_profile === "ASBIS_IT4PROFIT"
            ? form.imap_password || null
            : null,
        username_parameter:
          form.integration_profile === "ASBIS_IT4PROFIT"
            ? "USERNAME"
            : form.username_parameter,
        password_parameter:
          form.integration_profile === "ASBIS_IT4PROFIT"
            ? "PASSWORD"
            : form.password_parameter,
        api_key_parameter: form.api_key_parameter,
      });
    },
    onSuccess: () => {
      toast.success(
        "Pristupni podaci su promenjeni. Ponovite probno preuzimanje.",
      );
      setCredentialsOpen(false);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message),
  });
  const columns = useMemo<Column<Source>[]>(
    () => [
      {
        key: "supplier",
        label: "Dobavljač",
        tooltip: "Dobavljač kome konekcija pripada.",
        render: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id,
        csv: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id,
      },
      {
        key: "name",
        label: "Konekcija",
        tooltip: "Naziv načina na koji dobavljač isporučuje cenovnik.",
        render: (row) => <Typography fontWeight={650}>{row.name}</Typography>,
        csv: (row) => row.name,
      },
      {
        key: "source_type",
        label: "Način preuzimanja",
        tooltip: "Kanal kojim cenovnik dolazi u sistem.",
        render: displayMethod,
        csv: displayMethod,
      },
      {
        key: "format",
        label: "Format",
        tooltip: "Očekivani format dobavljačkog cenovnika.",
        render: displayFormat,
        csv: displayFormat,
      },
      {
        key: "status",
        label: "Status",
        tooltip: "Nacrt, aktivna konekcija ili arhiviran zapis.",
        render: (row) => (
          <StatusChip value={row.is_active ? row.status : "ARCHIVED"} />
        ),
        csv: (row) => row.status,
      },
      {
        key: "validation",
        label: "Poslednji test",
        tooltip: "Rezultat poslednjeg probnog preuzimanja.",
        render: (row) => (
          <StatusChip
            value={
              row.last_validation_status === "VALID"
                ? "READY"
                : row.last_validation_status === "INVALID"
                  ? "FAILED"
                  : "PENDING"
            }
          />
        ),
        csv: (row) => row.last_validation_status,
      },
    ],
    [supplierNames],
  );

  const update = (key: keyof ConnectionForm, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));
  const selectAuthenticationType = (value: string) =>
    setForm((current) => withAuthenticationType(current, value));
  const selectSoapProfile = (value: string) =>
    setForm((current) => withSoapProfile(current, value));
  const selectIntegrationProfile = (value: string) =>
    setForm((current) => withIntegrationProfile(current, value));
  const networkSupported = ["HTTP", "API", "PORTAL"].includes(form.method);
  const portalReady = isPortalReady(form);
  const certificateReady = isCertificateReady(
    form,
    certificateFile,
    draft?.credentials_available,
  );

  return (
    <>
      <PageHeader
        title="Konekcije dobavljača"
        description="Podesite kako sistem preuzima cenovnik dobavljača i proverite da li konekcija radi."
        actions={
          auth.can("supplier_sources.write") && (
            <Tooltip title="Pokrenite vođeno povezivanje dobavljača sa cenovnikom.">
              <Button
                variant="contained"
                startIcon={<AddRounded />}
                disabled={!workspace.supplierId}
                onClick={() => {
                  setForm(initialForm);
                  setDraft(null);
                  setProbe(null);
                  setProbeFile(null);
                  setStep(0);
                  setWizardOpen(true);
                }}
              >
                Poveži cenovnik
              </Button>
            </Tooltip>
          )
        }
      />
      <WorkspaceSelector requireSource={false} />
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", sm: "center" }}
        gap={1}
        mb={1}
      >
        {workspace.supplierId && (
          <FormControlLabel
            control={
              <Switch
                checked={showArchived}
                onChange={(event) => {
                  setShowArchived(event.target.checked);
                  setSelected([]);
                  setPage(0);
                }}
              />
            }
            label="Prikaži i arhivirane konekcije"
          />
        )}
        <Typography variant="caption" color="text.secondary">
          {workspace.supplierId
            ? "Prikazane su konekcije izabranog dobavljača."
            : "Prikazane su samo aktivne i uspešno testirane konekcije svih dobavljača."}
        </Typography>
      </Stack>
      <EntityTable
        tableId="sources"
        columns={columns}
        rows={sources.data?.items ?? []}
        total={sources.data?.total ?? 0}
        page={page}
        pageSize={25}
        loading={sources.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={setOpened}
        onRefresh={() => sources.refetch()}
        bulkActions={
          auth.can("supplier_sources.write") ? (
            <Tooltip title="Izabrane aktivne konekcije uklanja iz operativnog prikaza, ali čuva njihovu istoriju.">
              <span>
                <Button
                  size="small"
                  color="warning"
                  startIcon={<ArchiveRounded />}
                  disabled={
                    archiveSelected.isPending ||
                    !(sources.data?.items ?? []).some(
                      (source) =>
                        selected.includes(source.id) && source.is_active,
                    )
                  }
                  onClick={() => {
                    const count = (sources.data?.items ?? []).filter(
                      (source) =>
                        selected.includes(source.id) && source.is_active,
                    ).length;
                    if (
                      count > 0 &&
                      confirm(`Arhivirati ${count} izabranih konekcija?`)
                    ) {
                      archiveSelected.mutate();
                    }
                  }}
                >
                  Arhiviraj izabrane
                </Button>
              </span>
            </Tooltip>
          ) : undefined
        }
      />

      <DetailDrawer
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={opened?.name ?? ""}
        subtitle={
          opened ? `${displayMethod(opened)} · ${displayFormat(opened)}` : ""
        }
        actions={
          opened?.is_active ? (
            <>
              <Button
                component={Link}
                to={`/automation?supplier=${opened.supplier_id}&source=${opened.id}`}
                startIcon={<ScheduleRounded />}
              >
                Podesi raspored
              </Button>
              <Button
                startIcon={<CloudDownloadRounded />}
                onClick={async () => {
                  const result = await supplierApi.probeSource(
                    opened.supplier_id,
                    opened.id,
                  );
                  const refreshed = await supplierApi.source(
                    opened.supplier_id,
                    opened.id,
                  );
                  setProbe(result);
                  setProbeSourceId(opened.id);
                  setOpened(refreshed);
                  queryClient.invalidateQueries({ queryKey: ["sources"] });
                  if (result.successful) toast.success(result.message);
                  else toast.error(result.message);
                }}
              >
                Testiraj konekciju
              </Button>
              {opened.status === "DRAFT" &&
                opened.last_validation_status === "VALID" &&
                opened.last_validation_message?.startsWith("PROBE_OK:") && (
                  <Button
                    variant="contained"
                    startIcon={<CheckCircleRounded />}
                    disabled={activate.isPending}
                    onClick={() => activate.mutate(opened)}
                  >
                    Aktiviraj konekciju
                  </Button>
                )}
              <Button
                variant="contained"
                disabled={opened.status !== "ACTIVE"}
                title={
                  opened.status === "ACTIVE"
                    ? "Otvori analizu cenovnika"
                    : "Konekcija mora prvo biti uspešno testirana i aktivirana."
                }
                onClick={() => {
                  workspace.setSourceId(opened.id);
                  window.location.assign("/schemas");
                }}
              >
                Otvori analizu cenovnika
              </Button>
              {opened.status !== "ACTIVE" && (
                <Typography variant="caption" color="warning.main">
                  Pre analize uspešno testirajte i aktivirajte konekciju.
                </Typography>
              )}
              <Button
                startIcon={<KeyRounded />}
                onClick={() => {
                  const isEweApi =
                    String(opened.configuration.base_url ?? "") ===
                    "http://apicatalog.ewe.rs:5001/api/";
                  setForm((current) => ({
                    ...current,
                    authentication_type: String(
                      opened.configuration.authentication_type ?? "NONE",
                    ),
                    integration_profile: String(
                      opened.configuration.integration_profile ?? "GENERIC",
                    ),
                    pin_shop_id: String(opened.configuration.pin_shop_id ?? 4),
                    username: "",
                    password: "",
                    token: "",
                    api_key: "",
                    placement: isEweApi ? "QUERY" : current.placement,
                    username_parameter: isEweApi
                      ? "user"
                      : current.username_parameter,
                    password_parameter: isEweApi
                      ? "secretcode"
                      : current.password_parameter,
                    api_key_parameter:
                      opened.configuration.integration_profile === "PIN_SOAP"
                        ? "guid"
                        : current.api_key_parameter,
                  }));
                  setCredentialsOpen(true);
                }}
              >
                Promeni pristupne podatke
              </Button>
              <Button
                startIcon={<LinkRounded />}
                onClick={() => {
                  setForm(initialForm);
                  setDraft(null);
                  setProbe(null);
                  setStep(0);
                  setWizardOpen(true);
                }}
              >
                Promeni način
              </Button>
              <Button
                color="warning"
                startIcon={<ArchiveRounded />}
                onClick={() =>
                  confirm("Arhivirati ovu konekciju?") && archive.mutate(opened)
                }
              >
                Arhiviraj
              </Button>
            </>
          ) : undefined
        }
      >
        {opened && (
          <Stack gap={2}>
            <Alert
              severity={
                opened.has_secret_reference && !opened.credentials_available
                  ? "warning"
                  : opened.last_validation_status === "VALID"
                    ? "success"
                    : "info"
              }
            >
              {opened.has_secret_reference && !opened.credentials_available
                ? "Pristupni podaci više nisu dostupni. Unesite ih ponovo i ponovite probu."
                : opened.last_validation_message?.replace(
                    /^PROBE_(?:OK|FAILED): /,
                    "",
                  ) || "Konekcija još nije probno preuzela cenovnik."}
            </Alert>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="h6">Administrativni pregled</Typography>
              <Typography color="text.secondary" mt={0.5}>
                Centralna dijagnostika toka od konekcije do Delta obrade.
              </Typography>
            </Paper>
            <DetailSection title="Connection">
              <DetailRow
                label="Status"
                value={
                  <StatusChip
                    value={opened.is_active ? opened.status : "ARCHIVED"}
                  />
                }
              />
              <DetailRow label="Tip konekcije" value={displayMethod(opened)} />
              <DetailRow label="Format" value={displayFormat(opened)} />
            </DetailSection>
            <DetailSection title="Automatski raspored">
              <DetailRow
                label="Status"
                value={
                  <StatusChip value={sourceSchedule.data?.status ?? "MANUAL"} />
                }
              />
              <DetailRow
                label="Sledeće pokretanje"
                value={formatDate(sourceSchedule.data?.next_run_at)}
              />
              <DetailRow
                label="Poslednje pokretanje"
                value={formatDate(sourceSchedule.data?.last_run_at)}
              />
              <DetailRow
                label="Poslednji rezultat"
                value={sourceSchedule.data?.last_result ?? "Još nije izvršeno"}
              />
              <DetailRow
                label="Uzastopne greške"
                value={sourceSchedule.data?.consecutive_failures ?? 0}
              />
            </DetailSection>
            <DetailSection title="Last Probe">
              <DetailRow
                label="Datum"
                value={formatDate(opened.last_validation_at)}
              />
              <DetailRow
                label="Trajanje"
                value={
                  openedProbe
                    ? `${openedProbe.duration_ms} ms`
                    : "Detalji probe-a nisu trajno sačuvani."
                }
              />
              <DetailRow
                label="HTTP status"
                value={detailValue(
                  openedProbe?.http_status,
                  "HTTP status nije trajno sačuvan.",
                )}
              />
              <DetailRow
                label="Veličina odgovora"
                value={
                  openedProbe
                    ? `${openedProbe.size_bytes.toLocaleString("sr-RS")} B`
                    : "Veličina nije trajno sačuvana."
                }
              />
              <DetailRow
                label="XML validan"
                value={
                  openedProbe?.detected_format === "XML"
                    ? openedProbe.successful
                      ? "DA"
                      : "NE"
                    : openedProbe
                      ? "Nije XML format."
                      : "Rezultat formata nije trajno sačuvan."
                }
              />
            </DetailSection>
            <DetailSection title="Last Import">
              <DetailRow
                label="Broj proizvoda"
                value={detailValue(
                  acquisition?.accepted_record_count,
                  "Uspešan import još ne postoji.",
                )}
              />
              <DetailRow
                label="Broj kategorija"
                value="Acquisition ne beleži ovu metriku."
              />
              <DetailRow
                label="Broj slika"
                value="Acquisition ne beleži ovu metriku."
              />
              <DetailRow
                label="Broj opisa"
                value="Acquisition ne beleži ovu metriku."
              />
              <DetailRow
                label="Encoding"
                value="Encoding nije deo postojećeg Acquisition DTO-a."
              />
            </DetailSection>
            <DetailSection title="Schema">
              <DetailRow label="Postoji" value={schema ? "DA" : "NE"} />
              {schema ? (
                <>
                  <DetailRow
                    label="Schema ID"
                    value={String(schema.schema_code ?? schema.id)}
                  />
                  <DetailRow
                    label="Verzija"
                    value={detailValue(schema.version_number, "Nije dostupna.")}
                  />
                  <DetailRow
                    label="Status"
                    value={<StatusChip value={String(schema.status)} />}
                  />
                  <DetailRow
                    label="Field count"
                    value={detailValue(
                      schema.field_count,
                      "Schema postoji ali nije analizirana.",
                    )}
                  />
                  <DetailRow
                    label="Poslednja analiza"
                    value={formatDate(schema.updated_at)}
                  />
                  {Number(schema.field_count ?? 0) === 0 && (
                    <Alert severity="warning">
                      Schema postoji ali nije analizirana.
                    </Alert>
                  )}
                </>
              ) : (
                <Alert severity="info">Schema nije kreirana.</Alert>
              )}
            </DetailSection>
            <DetailSection title="Mapping">
              <DetailRow label="Postoji" value={mapping ? "DA" : "NE"} />
              {mapping ? (
                <>
                  <DetailRow
                    label="Mapping ID"
                    value={String(mapping.mapping_code ?? mapping.id)}
                  />
                  <DetailRow
                    label="Status"
                    value={<StatusChip value={String(mapping.status)} />}
                  />
                </>
              ) : (
                <Alert severity="info">
                  {schema
                    ? "Mapping nije napravljen."
                    : "Mapping nije moguć dok Schema nije kreirana."}
                </Alert>
              )}
            </DetailSection>
            <DetailSection title="Acquisition">
              <DetailRow label="Postoji" value={acquisition ? "DA" : "NE"} />
              {acquisition ? (
                <DetailRow
                  label="Status"
                  value={<StatusChip value={String(acquisition.status)} />}
                />
              ) : (
                <Alert severity="info">
                  {!schema
                    ? "Acquisition nije moguć dok Schema nije kreirana."
                    : !mapping
                      ? "Acquisition nije moguć dok Mapping nije napravljen."
                      : "Acquisition još nije pokrenut."}
                </Alert>
              )}
            </DetailSection>
            <DetailSection title="Snapshot">
              {snapshot ? (
                <>
                  <DetailRow
                    label="Snapshot ID"
                    value={String(snapshot.snapshot_code ?? snapshot.id)}
                  />
                  <DetailRow
                    label="Datum"
                    value={formatDate(
                      snapshot.finalized_at ?? snapshot.created_at,
                    )}
                  />
                </>
              ) : (
                <Alert severity="info">
                  {acquisition
                    ? "Snapshot još nije kreiran za obrađeni import."
                    : "Snapshot ne postoji jer Acquisition nije završen."}
                </Alert>
              )}
            </DetailSection>
            <DetailSection title="Delta">
              {delta ? (
                <>
                  <DetailRow
                    label="Poslednji Delta Run"
                    value={String(delta.delta_code ?? delta.id)}
                  />
                  <DetailRow
                    label="Broj izmena"
                    value={
                      Number(delta.added_items ?? 0) +
                      Number(delta.modified_items ?? 0) +
                      Number(delta.removed_items ?? 0)
                    }
                  />
                </>
              ) : (
                <Alert severity="info">
                  {snapshot
                    ? "Delta Run još nije pokrenut."
                    : "Delta nije moguć dok Snapshot ne postoji."}
                </Alert>
              )}
            </DetailSection>
          </Stack>
        )}
      </DetailDrawer>

      <SourceWizardDialog
        open={wizardOpen}
        step={step}
        form={form}
        draft={draft}
        probe={probe}
        probeFile={probeFile}
        certificateFile={certificateFile}
        networkSupported={networkSupported}
        portalReady={portalReady}
        certificateReady={certificateReady}
        savingDraft={saveDraft.isPending}
        testingConnection={testConnection.isPending}
        activating={activate.isPending}
        onClose={() => setWizardOpen(false)}
        setStep={setStep}
        onUpdate={update}
        onAuthenticationType={selectAuthenticationType}
        onSoapProfile={selectSoapProfile}
        onIntegrationProfile={selectIntegrationProfile}
        setProbeFile={setProbeFile}
        setCertificateFile={setCertificateFile}
        onSaveDraft={() => saveDraft.mutate()}
        onTestConnection={() => testConnection.mutate()}
        onActivate={(source) => activate.mutate(source)}
      />
      <SourceCredentialsDialog
        open={credentialsOpen}
        form={form}
        certificateFile={certificateFile}
        saving={changeCredentials.isPending}
        onClose={() => setCredentialsOpen(false)}
        onSave={() => changeCredentials.mutate()}
        onAuthenticationType={selectAuthenticationType}
        onUpdate={update}
        setCertificateFile={setCertificateFile}
      />
    </>
  );
}
