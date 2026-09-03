import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddRounded,
  ArchiveRounded,
  CancelRounded,
  CheckCircleRounded,
  CloudDownloadRounded,
  KeyRounded,
  LinkRounded,
  ScheduleRounded
} from "@mui/icons-material";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Switch,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
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

const methods = [
  ["HTTP", "Direktan URL", "Cenovnik je dostupan preko stabilne internet adrese."],
  ["PORTAL", "Portal sa prijavom", "Sistem se prijavljuje na B2B portal i zatim preuzima cenovnik."],
  ["API", "API dobavljača", "Dobavljač nudi servis za automatsko preuzimanje podataka."],
  ["FTP", "FTP", "Dobavljač ostavlja cenovnik na FTP serveru."],
  ["SFTP", "SFTP", "Bezbedno preuzimanje fajla sa udaljenog servera."],
  ["EMAIL", "Email", "Cenovnik stiže kao prilog email poruke."],
  ["GOOGLE_DRIVE", "Google Drive", "Dobavljač deli fajl ili folder preko Google Drive-a."],
  ["MANUAL_UPLOAD", "Ručno učitavanje", "Zaposleni preuzima fajl i učitava ga u aplikaciju."]
] as const;

const initialForm = {
  method: "HTTP",
  name: "",
  format: "AUTO",
  url: "",
  endpoint: "",
  login_url: "",
  login_submit_url: "",
  username_field: "username",
  password_field: "password",
  login_form_fields: "",
  http_method: "GET",
  login_required: false,
  placement: "HEADER",
  authentication_type: "NONE",
  integration_profile: "GENERIC",
  catalog_endpoint: "/B2BService/HTTP/Product/GetProductsList.aspx",
  price_endpoint: "/B2BService/HTTP/Product/GetProductsPriceList.aspx",
  barcode_service_url: "https://b2b.kimtec.rs/B2BService/B2BProductService.asmx",
  pin_shop_id: "4",
  certificate_password: "",
  username: "",
  password: "",
  imap_username: "",
  imap_password: "",
  token: "",
  api_key: "",
  username_parameter: "username",
  password_parameter: "password",
  api_key_parameter: "X-API-Key",
  public_query: "",
  public_headers: "",
  timeout: "30",
  verify_tls: true,
  host: "",
  port: "",
  remote_path: "/",
  filename_pattern: "*",
  mailbox: "",
  folder: "",
  sender: "",
  subject: "",
  received_hours: "24",
  imap_host: "mail.monitor.rs",
  imap_port: "993",
  file_id: "",
  folder_id: "",
  shared_drive_id: "",
  maximum_mb: "50",
  description: ""
};

type ConnectionForm = typeof initialForm;

function pairs(value: string): Record<string, string> {
  return Object.fromEntries(
    value
      .split("\n")
      .map((line) => line.split("=", 2).map((item) => item.trim()))
      .filter(([key, item]) => key && item)
  );
}

function sourcePayload(form: ConnectionForm): Record<string, unknown> {
  const timeout_seconds = Number(form.timeout);
  let source_type = form.method;
  let configuration: Record<string, unknown>;
  if (form.method === "PORTAL") {
    source_type = "API";
    configuration = {
      base_url: form.url,
      endpoint_path: null,
      http_method: "GET",
      authentication_type: "PORTAL_FORM",
      login_url: form.login_url,
      login_submit_url: form.login_submit_url || null,
      username_field: form.username_field,
      password_field: form.password_field,
      login_form_fields: pairs(form.login_form_fields),
      request_headers: pairs(form.public_headers),
      query_parameters: pairs(form.public_query),
      timeout_seconds,
      verify_tls: form.verify_tls
    };
  } else if (form.method === "HTTP" && form.login_required) {
    source_type = "API";
    configuration = {
      base_url: form.url,
      endpoint_path: null,
      http_method: form.http_method,
      authentication_type: form.authentication_type,
      request_headers: pairs(form.public_headers),
      query_parameters: pairs(form.public_query),
      timeout_seconds,
      verify_tls: form.verify_tls
    };
  } else if (form.method === "HTTP") {
    configuration = {
      url: form.url,
      http_method: form.http_method,
      request_headers: pairs(form.public_headers),
      query_parameters: pairs(form.public_query),
      timeout_seconds,
      verify_tls: form.verify_tls,
      expected_content_type: form.format
    };
  } else if (form.method === "API") {
    configuration = {
      base_url: form.url,
      endpoint_path: form.endpoint || null,
      http_method: form.http_method,
      authentication_type: form.authentication_type,
      request_headers: pairs(form.public_headers),
      query_parameters: pairs(form.public_query),
      timeout_seconds,
      verify_tls: form.verify_tls,
      integration_profile: form.integration_profile,
      pin_shop_id:
        form.integration_profile === "PIN_SOAP" ? Number(form.pin_shop_id) : 4,
      catalog_endpoint_path:
        ["KIMTEC_MSAN", "ASBIS_IT4PROFIT"].includes(form.integration_profile) ? form.catalog_endpoint : null,
      price_endpoint_path:
        ["KIMTEC_MSAN", "ASBIS_IT4PROFIT"].includes(form.integration_profile) ? form.price_endpoint : null,
      barcode_service_url:
        form.integration_profile === "KIMTEC_MSAN"
          ? form.barcode_service_url
          : null,
      imap_host: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_host : null,
      imap_port: form.integration_profile === "ASBIS_IT4PROFIT" ? Number(form.imap_port) : 993,
      // mail.monitor.rs currently requires OpenSSL legacy-DH compatibility.
      // Keep this scoped to the ASBIS integration; never lower TLS globally.
      imap_allow_legacy_dh: form.integration_profile === "ASBIS_IT4PROFIT",
      imap_folder: form.integration_profile === "ASBIS_IT4PROFIT" ? "INBOX" : "INBOX",
      imap_subject_filter: form.integration_profile === "ASBIS_IT4PROFIT" ? "ASBIS" : "ASBIS",
      imap_sender_filter: form.integration_profile === "ASBIS_IT4PROFIT" ? form.sender || null : null,
      imap_attachment_prefix: form.integration_profile === "ASBIS_IT4PROFIT" ? "HTML, PO actions, in mail body" : "HTML, PO actions, in mail body",
      imap_received_within_hours: form.integration_profile === "ASBIS_IT4PROFIT" ? 720 : 720
    };
  } else if (form.method === "FTP") {
    configuration = {
      host: form.host,
      port: Number(form.port || 21),
      username: form.username || null,
      remote_path: form.remote_path,
      passive_mode: true,
      use_tls: form.verify_tls,
      filename_pattern: form.filename_pattern,
      timeout_seconds
    };
  } else if (form.method === "SFTP") {
    configuration = {
      host: form.host,
      port: Number(form.port || 22),
      username: form.username,
      remote_path: form.remote_path,
      filename_pattern: form.filename_pattern,
      timeout_seconds
    };
  } else if (form.method === "EMAIL") {
    configuration = {
      mailbox: form.mailbox,
      folder: form.folder || null,
      sender_filter: form.sender || null,
      subject_filter: form.subject || null,
      attachment_filename_pattern: form.filename_pattern,
      received_within_hours: Number(form.received_hours)
    };
  } else if (form.method === "GOOGLE_DRIVE") {
    configuration = {
      file_id: form.file_id || null,
      folder_id: form.folder_id || null,
      filename_pattern: form.filename_pattern || null,
      shared_drive_id: form.shared_drive_id || null
    };
  } else {
    configuration = {
      accepted_file_types:
        form.format === "AUTO" ? ["CSV", "EXCEL", "XML", "JSON"] : [form.format],
      maximum_file_size_mb: Number(form.maximum_mb),
      filename_pattern: form.filename_pattern || null
    };
  }
  return {
    name: form.name,
    source_type,
    configuration,
    description: form.description || null,
    status: "DRAFT"
  };
}

function displayMethod(source: Source): string {
  if (source.source_type === "HTTP") return "Direktan URL";
  if (source.configuration.authentication_type === "PORTAL_FORM") {
    return "Portal sa prijavom";
  }
  if (source.source_type === "API") return "API / zaštićeni URL";
  if (source.source_type === "MANUAL_UPLOAD") return "Ručno učitavanje";
  return source.source_type;
}

function displayFormat(source: Source): string {
  const configured = source.configuration.expected_content_type;
  if (typeof configured === "string") return configured;
  const accepted = source.configuration.accepted_file_types;
  if (Array.isArray(accepted)) return accepted.join(", ");
  return ["CSV", "EXCEL", "XML"].includes(source.source_type)
    ? source.source_type
    : "Automatski";
}

function formatDate(value: unknown): string {
  return typeof value === "string"
    ? new Intl.DateTimeFormat("sr-RS", {
        dateStyle: "medium",
        timeStyle: "short"
      }).format(new Date(value))
    : "Nije dostupno";
}

function detailValue(value: unknown, reason: string): string {
  return value === null || value === undefined || value === ""
    ? reason
    : String(value);
}

function DetailSection({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="h6" mb={1.5}>{title}</Typography>
      <Stack gap={1}>{children}</Stack>
    </Paper>
  );
}

function DetailRow({
  label,
  value
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      justifyContent="space-between"
      gap={0.5}
    >
      <Typography color="text.secondary">{label}</Typography>
      <Typography fontWeight={600} textAlign={{ sm: "right" }}>
        {value}
      </Typography>
    </Stack>
  );
}

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
        active_only: true
      })
  });
  const supplierNames = useMemo(
    () =>
      new Map(
        (suppliers.data?.items ?? []).map((supplier) => [
          supplier.id,
          `${supplier.supplier_code} · ${supplier.company_name}`
        ])
      ),
    [suppliers.data?.items]
  );
  const sources = useQuery({
    queryKey: [
      "sources",
      workspace.supplierId || "all-ready",
      page,
      showArchived,
      suppliers.data?.items.map((supplier) => supplier.id).join(",")
    ],
    queryFn: async () => {
      if (workspace.supplierId) {
        return supplierApi.sources(workspace.supplierId, {
          limit: 25,
          offset: page * 25,
          active_only: !showArchived
        });
      }
      const pages = await Promise.all(
        (suppliers.data?.items ?? []).map((supplier) =>
          supplierApi.sources(supplier.id, {
            limit: 500,
            offset: 0,
            active_only: true,
            status: "ACTIVE"
          })
        )
      );
      const ready = pages
        .flatMap((result) => result.items)
        .filter(
          (source) =>
            source.is_active &&
            source.status === "ACTIVE" &&
            source.last_validation_status === "VALID"
        )
        .sort((left, right) => left.name.localeCompare(right.name, "sr"));
      return {
        items: ready.slice(page * 25, page * 25 + 25),
        total: ready.length
      };
    },
    enabled: Boolean(workspace.supplierId || suppliers.data),
    placeholderData: (previous) => previous
  });
  const sourceRoot = opened
    ? `/suppliers/${opened.supplier_id}/sources/${opened.id}`
    : "";
  const sourceSchedule = useQuery({
    queryKey: ["source-details", "schedule", opened?.id],
    queryFn: () => supplierApi.schedule(opened!.supplier_id, opened!.id),
    enabled: Boolean(opened)
  });
  const schemas = useQuery({
    queryKey: ["source-details", "schemas", opened?.id],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `${sourceRoot}/schema-profiles`,
        { limit: 100, offset: 0 }
      ),
    enabled: Boolean(opened)
  });
  const schema = schemas.data?.items.find((item) => item.status === "ACTIVE")
    ?? schemas.data?.items[0];
  const mappings = useQuery({
    queryKey: ["source-details", "mappings", opened?.id, schema?.id],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `${sourceRoot}/schema-profiles/${schema?.id}/mapping-profiles`,
        { limit: 100, offset: 0 }
      ),
    enabled: Boolean(opened && schema)
  });
  const mapping = mappings.data?.items.find((item) => item.status === "ACTIVE")
    ?? mappings.data?.items[0];
  const acquisitions = useQuery({
    queryKey: ["source-details", "acquisitions", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "acquisitions",
        { limit: 1, offset: 0 }
      ),
    enabled: Boolean(opened)
  });
  const snapshots = useQuery({
    queryKey: ["source-details", "snapshots", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "snapshots",
        { limit: 1, offset: 0 }
      ),
    enabled: Boolean(opened)
  });
  const deltas = useQuery({
    queryKey: ["source-details", "deltas", opened?.id],
    queryFn: () =>
      supplierApi.collection<Operation>(
        opened!.supplier_id,
        opened!.id,
        "deltas",
        { limit: 1, offset: 0 }
      ),
    enabled: Boolean(opened)
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
            version: draft.version
          })
        : await supplierApi.createSource(workspace.supplierId, sourcePayload(form));
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
        await supplierApi.writeSourceCredentials(workspace.supplierId, source.id, {
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
          imap_username: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_username || null : null,
          imap_password: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_password || null : null,
          username_parameter: form.integration_profile === "ASBIS_IT4PROFIT" ? "USERNAME" : form.username_parameter,
          password_parameter: form.integration_profile === "ASBIS_IT4PROFIT" ? "PASSWORD" : form.password_parameter,
          api_key_parameter: form.api_key_parameter
        });
        return supplierApi.source(workspace.supplierId, source.id);
      }
      if (form.authentication_type === "CLIENT_CERTIFICATE" && certificateFile) {
        await supplierApi.writeSourceCertificate(
          workspace.supplierId,
          source.id,
          certificateFile,
          form.certificate_password
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
    onError: (error: ApiError) => toast.error(error.message)
  });

  const testConnection = useMutation({
    mutationFn: async () => {
      const source = await saveDraft.mutateAsync();
      const result =
        form.method === "MANUAL_UPLOAD" && probeFile
          ? await supplierApi.probeUploadedSource(
              workspace.supplierId,
              source.id,
              probeFile
            )
          : await supplierApi.probeSource(workspace.supplierId, source.id);
      const refreshed = await supplierApi.source(workspace.supplierId, source.id);
      return { result, refreshed };
    },
    onSuccess: ({ result, refreshed }) => {
      setDraft(refreshed);
      setProbe(result);
      setProbeSourceId(refreshed.id);
      setStep(2);
      if (result.successful) toast.success("Cenovnik je uspešno probno preuzet.");
      else toast.error(result.message);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const activate = useMutation({
    mutationFn: async (source: Source) =>
      supplierApi.updateSource(source.supplier_id, source.id, {
        version: source.version,
        status: "ACTIVE"
      }),
    onSuccess: (source) => {
      toast.success("Konekcija je aktivirana.");
      setDraft(source);
      setOpened(source);
      setStep(3);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });

  const archive = useMutation({
    mutationFn: (source: Source) =>
      supplierApi.deactivateSource(source.supplier_id, source.id),
    onSuccess: () => {
      toast.success("Konekcija je arhivirana.");
      setOpened(null);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });
  const archiveSelected = useMutation({
    mutationFn: async () => {
      const rows = (sources.data?.items ?? []).filter(
        (source) => selected.includes(source.id) && source.is_active
      );
      const results = await Promise.allSettled(
        rows.map((source) =>
          supplierApi.deactivateSource(source.supplier_id, source.id)
        )
      );
      return {
        archived: results.filter((result) => result.status === "fulfilled").length,
        failed: results.filter((result) => result.status === "rejected").length
      };
    },
    onSuccess: ({ archived, failed }) => {
      if (archived) toast.success(`${archived} konekcija je arhivirano.`);
      if (failed) toast.error(`${failed} konekcija nije moguće arhivirati.`);
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    }
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
          form.certificate_password
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
        imap_username: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_username || null : null,
        imap_password: form.integration_profile === "ASBIS_IT4PROFIT" ? form.imap_password || null : null,
        username_parameter: form.integration_profile === "ASBIS_IT4PROFIT" ? "USERNAME" : form.username_parameter,
        password_parameter: form.integration_profile === "ASBIS_IT4PROFIT" ? "PASSWORD" : form.password_parameter,
        api_key_parameter: form.api_key_parameter
      });
    },
    onSuccess: () => {
      toast.success("Pristupni podaci su promenjeni. Ponovite probno preuzimanje.");
      setCredentialsOpen(false);
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
    onError: (error: ApiError) => toast.error(error.message)
  });
  const columns = useMemo<Column<Source>[]>(
    () => [
      {
        key: "supplier",
        label: "Dobavljač",
        tooltip: "Dobavljač kome konekcija pripada.",
        render: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id,
        csv: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id
      },
      {
        key: "name",
        label: "Konekcija",
        tooltip: "Naziv načina na koji dobavljač isporučuje cenovnik.",
        render: (row) => <Typography fontWeight={650}>{row.name}</Typography>,
        csv: (row) => row.name
      },
      {
        key: "source_type",
        label: "Način preuzimanja",
        tooltip: "Kanal kojim cenovnik dolazi u sistem.",
        render: displayMethod,
        csv: displayMethod
      },
      {
        key: "format",
        label: "Format",
        tooltip: "Očekivani format dobavljačkog cenovnika.",
        render: displayFormat,
        csv: displayFormat
      },
      {
        key: "status",
        label: "Status",
        tooltip: "Nacrt, aktivna konekcija ili arhiviran zapis.",
        render: (row) => <StatusChip value={row.is_active ? row.status : "ARCHIVED"} />,
        csv: (row) => row.status
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
        csv: (row) => row.last_validation_status
      }
    ],
    [supplierNames]
  );

  const update = (key: keyof ConnectionForm, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));
  const selectAuthenticationType = (value: string) =>
    setForm((current) =>
      value === "SOAP_BODY"
        ? {
            ...current,
            authentication_type: value,
            integration_profile: "CT_SOAP",
            placement: "SOAP_BODY",
            http_method: "POST",
            format: "JSON",
            url: current.url || "https://www.ct4partners.com/WS/CTProductsInStock.asmx",
            endpoint: "",
            name: current.name || "CT SOAP cenovnik"
          }
        : {
            ...current,
            authentication_type: value,
            integration_profile:
              current.integration_profile === "CT_SOAP"
                ? "GENERIC"
                : current.integration_profile,
            placement: current.placement === "SOAP_BODY" ? "HEADER" : current.placement
          }
    );
  const selectSoapProfile = (value: string) =>
    setForm((current) =>
      value === "PIN_SOAP"
        ? {
            ...current,
            integration_profile: value,
            authentication_type: "SOAP_BODY",
            placement: "SOAP_BODY",
            http_method: "POST",
            format: "JSON",
            url: "https://partner.pinsoft.com/b2b/services/stock-webservice",
            endpoint: "",
            api_key_parameter: "guid",
            name: current.name || "PIN / ALSO cenovnik"
          }
        : {
            ...current,
            integration_profile: "CT_SOAP",
            authentication_type: "SOAP_BODY",
            placement: "SOAP_BODY",
            http_method: "POST",
            format: "JSON",
            url: "https://www.ct4partners.com/WS/CTProductsInStock.asmx",
            endpoint: "",
            api_key_parameter: "X-API-Key"
          }
    );
  const selectIntegrationProfile = (value: string) =>
    setForm((current) =>
      value === "ASBIS_IT4PROFIT"
        ? {
            ...current,
            integration_profile: value,
            authentication_type: "BASIC",
            placement: "QUERY",
            url: "https://services.it4profit.com/product/sr/710",
            endpoint: "",
            catalog_endpoint: "ProductList.xml",
            price_endpoint: "PriceAvail.xml",
            username_parameter: "USERNAME",
            password_parameter: "PASSWORD",
            imap_host: "mail.monitor.rs",
            imap_port: "993",
            imap_username: "",
            format: "JSON",
            name: current.name || "ASBIS - objedinjeni cenovnik"
          }
        : value === "KIMTEC_MSAN"
        ? {
            ...current,
            integration_profile: value,
            url: "https://b2b.kimtec.rs",
            endpoint: "",
            format: "JSON",
            barcode_service_url:
              "https://b2b.kimtec.rs/B2BService/B2BProductService.asmx",
            name: current.name || "KimTec / M SAN - kompletan cenovnik"
          }
        : { ...current, integration_profile: value }
    );
  const networkSupported = ["HTTP", "API", "PORTAL"].includes(form.method);
  const portalReady =
    form.method !== "PORTAL" ||
    Boolean(
      form.url.trim() &&
        form.login_url.trim() &&
        form.username_field.trim() &&
        form.password_field.trim() &&
        form.username.trim() &&
        form.password
    );
  const certificateReady =
    form.authentication_type !== "CLIENT_CERTIFICATE" ||
    Boolean(
      (certificateFile && form.certificate_password) || draft?.credentials_available
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
                      (source) => selected.includes(source.id) && source.is_active
                    )
                  }
                  onClick={() => {
                    const count = (sources.data?.items ?? []).filter(
                      (source) => selected.includes(source.id) && source.is_active
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
        subtitle={opened ? `${displayMethod(opened)} · ${displayFormat(opened)}` : ""}
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
                  const result = await supplierApi.probeSource(opened.supplier_id, opened.id);
                  const refreshed = await supplierApi.source(
                    opened.supplier_id,
                    opened.id
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
                      opened.configuration.authentication_type ?? "NONE"
                    ),
                    integration_profile: String(
                      opened.configuration.integration_profile ?? "GENERIC"
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
                        : current.api_key_parameter
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
                onClick={() => confirm("Arhivirati ovu konekciju?") && archive.mutate(opened)}
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
                : opened.last_validation_message?.replace(/^PROBE_(?:OK|FAILED): /, "") ||
                  "Konekcija još nije probno preuzela cenovnik."}
            </Alert>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="h6">Administrativni pregled</Typography>
              <Typography color="text.secondary" mt={0.5}>
                Centralna dijagnostika toka od konekcije do Delta obrade.
              </Typography>
            </Paper>
            <DetailSection title="Connection">
              <DetailRow label="Status" value={<StatusChip value={opened.is_active ? opened.status : "ARCHIVED"} />} />
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
              <DetailRow label="Datum" value={formatDate(opened.last_validation_at)} />
              <DetailRow
                label="Trajanje"
                value={openedProbe ? `${openedProbe.duration_ms} ms` : "Detalji probe-a nisu trajno sačuvani."}
              />
              <DetailRow
                label="HTTP status"
                value={detailValue(openedProbe?.http_status, "HTTP status nije trajno sačuvan.")}
              />
              <DetailRow
                label="Veličina odgovora"
                value={openedProbe ? `${openedProbe.size_bytes.toLocaleString("sr-RS")} B` : "Veličina nije trajno sačuvana."}
              />
              <DetailRow
                label="XML validan"
                value={
                  openedProbe?.detected_format === "XML"
                    ? openedProbe.successful ? "DA" : "NE"
                    : openedProbe ? "Nije XML format." : "Rezultat formata nije trajno sačuvan."
                }
              />
            </DetailSection>
            <DetailSection title="Last Import">
              <DetailRow
                label="Broj proizvoda"
                value={detailValue(acquisition?.accepted_record_count, "Uspešan import još ne postoji.")}
              />
              <DetailRow label="Broj kategorija" value="Acquisition ne beleži ovu metriku." />
              <DetailRow label="Broj slika" value="Acquisition ne beleži ovu metriku." />
              <DetailRow label="Broj opisa" value="Acquisition ne beleži ovu metriku." />
              <DetailRow label="Encoding" value="Encoding nije deo postojećeg Acquisition DTO-a." />
            </DetailSection>
            <DetailSection title="Schema">
              <DetailRow label="Postoji" value={schema ? "DA" : "NE"} />
              {schema ? (
                <>
                  <DetailRow label="Schema ID" value={String(schema.schema_code ?? schema.id)} />
                  <DetailRow label="Verzija" value={detailValue(schema.version_number, "Nije dostupna.")} />
                  <DetailRow label="Status" value={<StatusChip value={String(schema.status)} />} />
                  <DetailRow label="Field count" value={detailValue(schema.field_count, "Schema postoji ali nije analizirana.")} />
                  <DetailRow label="Poslednja analiza" value={formatDate(schema.updated_at)} />
                  {Number(schema.field_count ?? 0) === 0 && (
                    <Alert severity="warning">Schema postoji ali nije analizirana.</Alert>
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
                  <DetailRow label="Mapping ID" value={String(mapping.mapping_code ?? mapping.id)} />
                  <DetailRow label="Status" value={<StatusChip value={String(mapping.status)} />} />
                </>
              ) : (
                <Alert severity="info">
                  {schema ? "Mapping nije napravljen." : "Mapping nije moguć dok Schema nije kreirana."}
                </Alert>
              )}
            </DetailSection>
            <DetailSection title="Acquisition">
              <DetailRow label="Postoji" value={acquisition ? "DA" : "NE"} />
              {acquisition ? (
                <DetailRow label="Status" value={<StatusChip value={String(acquisition.status)} />} />
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
                  <DetailRow label="Snapshot ID" value={String(snapshot.snapshot_code ?? snapshot.id)} />
                  <DetailRow label="Datum" value={formatDate(snapshot.finalized_at ?? snapshot.created_at)} />
                </>
              ) : (
                <Alert severity="info">
                  {acquisition ? "Snapshot još nije kreiran za obrađeni import." : "Snapshot ne postoji jer Acquisition nije završen."}
                </Alert>
              )}
            </DetailSection>
            <DetailSection title="Delta">
              {delta ? (
                <>
                  <DetailRow label="Poslednji Delta Run" value={String(delta.delta_code ?? delta.id)} />
                  <DetailRow
                    label="Broj izmena"
                    value={
                      Number(delta.added_items ?? 0)
                      + Number(delta.modified_items ?? 0)
                      + Number(delta.removed_items ?? 0)
                    }
                  />
                </>
              ) : (
                <Alert severity="info">
                  {snapshot ? "Delta Run još nije pokrenut." : "Delta nije moguć dok Snapshot ne postoji."}
                </Alert>
              )}
            </DetailSection>
          </Stack>
        )}
      </DetailDrawer>

      <Dialog open={wizardOpen} onClose={() => setWizardOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>Povezivanje dobavljača sa cenovnikom</DialogTitle>
        <DialogContent>
          <Stepper activeStep={step} sx={{ py: 2 }}>
            {["Način preuzimanja", "Podaci", "Probno preuzimanje", "Aktivacija"].map((label) => (
              <Step key={label}><StepLabel>{label}</StepLabel></Step>
            ))}
          </Stepper>
          {step === 0 && (
            <Grid container spacing={2}>
              {methods.map(([value, title, description]) => (
                <Grid item xs={12} sm={6} key={value}>
                  <Card
                    variant="outlined"
                    sx={(theme) => ({
                      height: "100%",
                      borderWidth: form.method === value ? 2 : 1,
                      borderColor:
                        form.method === value
                          ? "primary.main"
                          : "divider",
                      bgcolor:
                        form.method === value
                          ? theme.palette.action.selected
                          : "background.paper",
                      transition:
                        "border-color 150ms ease, background-color 150ms ease"
                    })}
                  >
                    <CardActionArea onClick={() => update("method", value)}>
                      <CardContent>
                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                          <Typography variant="h6">{title}</Typography>
                          {form.method === value && (
                            <CheckCircleRounded color="primary" aria-label="Izabrano" />
                          )}
                        </Stack>
                        <Typography color="text.secondary" variant="body2" mt={1}>
                          {description}
                        </Typography>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
          {step === 1 && (
            <Stack gap={2} mt={1}>
              <TextField
                label="Naziv konekcije"
                required
                value={form.name}
                helperText="Na primer: Glavni XML cenovnik."
                onChange={(event) => update("name", event.target.value)}
              />
              {["HTTP", "API", "PORTAL", "MANUAL_UPLOAD"].includes(form.method) && (
                <TextField
                  select
                  label="Format cenovnika"
                  value={form.format}
                  helperText="Izaberite format ili dozvolite automatsko prepoznavanje."
                  onChange={(event) => update("format", event.target.value)}
                >
                  {["AUTO", "XML", "EXCEL", "CSV", "JSON"].map((item) => (
                    <MenuItem key={item} value={item}>{item === "AUTO" ? "Automatsko prepoznavanje" : item}</MenuItem>
                  ))}
                </TextField>
              )}
              {["HTTP", "API", "PORTAL"].includes(form.method) && (
                <>
                  <TextField
                    label={form.method === "API" ? "Osnovni URL" : "URL za preuzimanje"}
                    required
                    value={form.url}
                    helperText="Adresa sa koje sistem preuzima cenovnik."
                    onChange={(event) => update("url", event.target.value)}
                  />
                  {form.method === "API" && (
                    <>
                      <TextField select label="Profil integracije" value={form.integration_profile} onChange={(event) => selectIntegrationProfile(event.target.value)}>
                        <MenuItem value="GENERIC">Opšti API</MenuItem>
                        <MenuItem value="ASBIS_IT4PROFIT">ASBIS (2 XML + akcije iz emaila)</MenuItem>
                        <MenuItem value="KIMTEC_MSAN">KimTec / M SAN B2B</MenuItem>
                      </TextField>
                      {form.integration_profile === "ASBIS_IT4PROFIT" ? (
                        <>
                          <Alert severity="info">Katalog i stanje/cene spajaju se sa poslednjim ASBIS akcijskim ZIP prilogom po šifri artikla.</Alert>
                          <TextField label="Prvi XML — katalog proizvoda" value={form.catalog_endpoint} helperText={`${form.url.replace(/\/$/, "")}/${form.catalog_endpoint.replace(/^\//, "")} (USERNAME i PASSWORD sistem dodaje bez prikazivanja)`} onChange={(event) => update("catalog_endpoint", event.target.value)} />
                          <TextField label="Drugi XML — cene i stanje" value={form.price_endpoint} helperText={`${form.url.replace(/\/$/, "")}/${form.price_endpoint.replace(/^\//, "")} (USERNAME i PASSWORD sistem dodaje bez prikazivanja)`} onChange={(event) => update("price_endpoint", event.target.value)} />
                          <TextField label="IMAP server" value={form.imap_host} onChange={(event) => update("imap_host", event.target.value)} />
                          <TextField label="IMAP port" value={form.imap_port} onChange={(event) => update("imap_port", event.target.value)} />
                          <TextField label="Dozvoljeni pošiljalac" value={form.sender} helperText="Opciono, ali preporučeno: email adresa ili stabilan deo From zaglavlja ASBIS poruke." onChange={(event) => update("sender", event.target.value)} />
                          <TextField label="IMAP korisničko ime" value={form.imap_username} onChange={(event) => update("imap_username", event.target.value)} />
                          <TextField type="password" label="IMAP lozinka" value={form.imap_password} onChange={(event) => update("imap_password", event.target.value)} />
                        </>
                      ) : (
                        <TextField label="Endpoint" value={form.endpoint} helperText="Putanja API operacije, na primer /v1/products." onChange={(event) => update("endpoint", event.target.value)} />
                      )}
                    </>
                  )}
                  {form.method === "PORTAL" && (
                    <>
                      <Alert severity="info">
                        Sistem otvara login stranicu, čuva session cookie samo tokom
                        ovog izvršavanja i zatim preuzima cenovnik.
                      </Alert>
                      <TextField
                        label="URL stranice za prijavu"
                        required
                        value={form.login_url}
                        helperText="Adresa na kojoj se prikazuje forma za prijavu na B2B portal."
                        onChange={(event) => update("login_url", event.target.value)}
                      />
                      <TextField
                        label="Korisničko ime"
                        required
                        value={form.username}
                        onChange={(event) => update("username", event.target.value)}
                      />
                      <TextField
                        type="password"
                        label="Lozinka"
                        required
                        value={form.password}
                        onChange={(event) => update("password", event.target.value)}
                      />
                    </>
                  )}
                  {form.method !== "PORTAL" && (
                    <FormControlLabel
                      control={<Switch checked={form.login_required || form.method === "API"} onChange={(event) => update("login_required", event.target.checked)} disabled={form.method === "API"} />}
                      label="Potrebna je prijava"
                    />
                  )}
                  {form.method !== "PORTAL" && (form.login_required || form.method === "API") && (
                    <>
                      <TextField
                        select
                        label="Način prijave"
                        value={form.authentication_type}
                        onChange={(event) => selectAuthenticationType(event.target.value)}
                      >
                        <MenuItem value="NONE">Bez prijave</MenuItem>
                        <MenuItem value="BASIC">Korisničko ime i lozinka</MenuItem>
                        <MenuItem value="BEARER">Bearer token</MenuItem>
                        <MenuItem value="API_KEY">API ključ</MenuItem>
                        <MenuItem value="CLIENT_CERTIFICATE">Klijentski sertifikat (mTLS)</MenuItem>
                        <MenuItem value="SOAP_BODY">SOAP servis (CT / PIN-ALSO)</MenuItem>
                      </TextField>
                      {form.integration_profile !== "ASBIS_IT4PROFIT" && !(["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(form.authentication_type)) && (
                        <TextField select label="Gde dobavljač očekuje podatke za prijavu" value={form.placement} onChange={(event) => update("placement", event.target.value)}>
                          <MenuItem value="HEADER">Bezbednosno zaglavlje</MenuItem>
                          <MenuItem value="QUERY">Parametri adrese (npr. DS Computers)</MenuItem>
                        </TextField>
                      )}
                      {form.integration_profile === "ASBIS_IT4PROFIT" && (
                        <Alert severity="info">ASBIS API prijava je fiksno podešena kroz URL parametre USERNAME i PASSWORD.</Alert>
                      )}
                      {(form.authentication_type === "BASIC" ||
                        form.authentication_type === "API_KEY" ||
                        (form.authentication_type === "SOAP_BODY" &&
                          form.integration_profile === "CT_SOAP")) && (
                        <TextField label="Korisničko ime" value={form.username} onChange={(event) => update("username", event.target.value)} />
                      )}
                      {(form.authentication_type === "BASIC" ||
                        (form.authentication_type === "SOAP_BODY" &&
                          form.integration_profile === "CT_SOAP")) && (
                        <TextField type="password" label="Lozinka" value={form.password} onChange={(event) => update("password", event.target.value)} />
                      )}
                      {form.authentication_type === "SOAP_BODY" && (
                        <>
                          <TextField select label="SOAP profil integracije" value={form.integration_profile} onChange={(event) => selectSoapProfile(event.target.value)}>
                            <MenuItem value="CT_SOAP">CT Computers</MenuItem>
                            <MenuItem value="PIN_SOAP">PIN / ALSO Srbija</MenuItem>
                          </TextField>
                          {form.integration_profile === "PIN_SOAP" ? (
                            <>
                              <Alert severity="info">Preuzimaju se samo artikli koje PIN/ALSO označi kao dostupne na stanju. GUID se trajno čuva van baze.</Alert>
                              <TextField label="Klijentski kod (GUID)" type="password" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} />
                              <TextField label="Shop ID" value={form.pin_shop_id} onChange={(event) => update("pin_shop_id", event.target.value)} helperText="Podrazumevana vrednost prema dokumentaciji je 4." />
                            </>
                          ) : (
                            <Alert severity="info">Pristupni podaci se trajno čuvaju van baze. Sistem ih šalje samo unutar CT SOAP zahteva; javna IP adresa aplikacije mora biti odobrena kod dobavljača.</Alert>
                          )}
                        </>
                      )}
                      {form.authentication_type === "BEARER" && (
                        <TextField type="password" label="Token" value={form.token} onChange={(event) => update("token", event.target.value)} />
                      )}
                      {form.authentication_type === "API_KEY" && (
                        <TextField type="password" label="API ključ ili lozinka" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} />
                      )}
                      {form.authentication_type === "CLIENT_CERTIFICATE" && (
                        <>
                          <TextField select label="Profil integracije" value={form.integration_profile} onChange={(event) => selectIntegrationProfile(event.target.value)}>
                            <MenuItem value="GENERIC">Opšti mTLS API</MenuItem>
                            <MenuItem value="KIMTEC_MSAN">KimTec / M SAN B2B</MenuItem>
                          </TextField>
                          {form.integration_profile === "KIMTEC_MSAN" && (
                            <>
                              <Alert severity="info">Sistem preuzima katalog, cenovnik i EAN barkodove istim sertifikatom i spaja ih po ProductCode.</Alert>
                              <TextField label="Endpoint kataloga" value={form.catalog_endpoint} onChange={(event) => update("catalog_endpoint", event.target.value)} />
                              <TextField label="Endpoint cenovnika" value={form.price_endpoint} onChange={(event) => update("price_endpoint", event.target.value)} />
                              <TextField label="SOAP servis za EAN barkodove" value={form.barcode_service_url} onChange={(event) => update("barcode_service_url", event.target.value)} />
                            </>
                          )}
                          <Button component="label" variant="outlined">
                            {certificateFile ? certificateFile.name : "Izaberi .p12 / .pfx sertifikat"}
                            <input hidden type="file" accept=".p12,.pfx,application/x-pkcs12" onChange={(event) => setCertificateFile(event.target.files?.[0] ?? null)} />
                          </Button>
                          <TextField type="password" label="Lozinka sertifikata" value={form.certificate_password} helperText="Unosi se samo pri prvom čuvanju ili zameni sertifikata." onChange={(event) => update("certificate_password", event.target.value)} />
                        </>
                      )}
                      {!(["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(form.authentication_type)) && form.placement === "QUERY" && (
                        <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                          <TextField fullWidth label="Naziv parametra korisničkog imena" value={form.username_parameter} onChange={(event) => update("username_parameter", event.target.value)} />
                          <TextField fullWidth label="Naziv parametra lozinke" value={form.password_parameter} onChange={(event) => update("password_parameter", event.target.value)} />
                        </Stack>
                      )}
                    </>
                  )}
                </>
              )}
              {["FTP", "SFTP"].includes(form.method) && (
                <>
                  <TextField label="Server" required value={form.host} onChange={(event) => update("host", event.target.value)} />
                  <TextField label="Port" value={form.port} helperText="Ostavite prazno za standardni port." onChange={(event) => update("port", event.target.value)} />
                  <TextField label="Korisničko ime" value={form.username} onChange={(event) => update("username", event.target.value)} />
                  <TextField type="password" label="Lozinka ili ključ" value={form.password} onChange={(event) => update("password", event.target.value)} />
                  <TextField label="Udaljena putanja" value={form.remote_path} onChange={(event) => update("remote_path", event.target.value)} />
                  <TextField label="Šablon naziva fajla" value={form.filename_pattern} onChange={(event) => update("filename_pattern", event.target.value)} />
                </>
              )}
              {form.method === "EMAIL" && (
                <>
                  <TextField label="Mailbox" required value={form.mailbox} onChange={(event) => update("mailbox", event.target.value)} />
                  <TextField label="Folder" value={form.folder} onChange={(event) => update("folder", event.target.value)} />
                  <TextField label="Pošiljalac" value={form.sender} onChange={(event) => update("sender", event.target.value)} />
                  <TextField label="Deo naslova poruke" value={form.subject} onChange={(event) => update("subject", event.target.value)} />
                  <TextField label="Šablon naziva priloga" required value={form.filename_pattern} onChange={(event) => update("filename_pattern", event.target.value)} />
                  <TextField type="password" label="Pristupni podaci" value={form.password} onChange={(event) => update("password", event.target.value)} />
                </>
              )}
              {form.method === "GOOGLE_DRIVE" && (
                <>
                  <TextField label="File ID" value={form.file_id} onChange={(event) => update("file_id", event.target.value)} />
                  <TextField label="Folder ID" value={form.folder_id} onChange={(event) => update("folder_id", event.target.value)} />
                  <TextField label="Šablon naziva fajla" value={form.filename_pattern} onChange={(event) => update("filename_pattern", event.target.value)} />
                  <TextField label="Shared Drive ID" value={form.shared_drive_id} onChange={(event) => update("shared_drive_id", event.target.value)} />
                </>
              )}
              {form.method === "MANUAL_UPLOAD" && (
                <>
                  <TextField label="Maksimalna veličina fajla (MB)" value={form.maximum_mb} onChange={(event) => update("maximum_mb", event.target.value)} />
                  <TextField label="Šablon naziva fajla" value={form.filename_pattern} onChange={(event) => update("filename_pattern", event.target.value)} />
                  <Button component="label" variant="outlined">
                    {probeFile ? probeFile.name : "Izaberi probni fajl"}
                    <input
                      hidden
                      type="file"
                      accept=".xml,.csv,.xlsx"
                      onChange={(event) =>
                        setProbeFile(event.target.files?.[0] ?? null)
                      }
                    />
                  </Button>
                  <Typography variant="caption" color="text.secondary">
                    Probni fajl se analizira u memoriji i ne pokreće Acquisition.
                  </Typography>
                </>
              )}
              <Accordion>
                <AccordionSummary>Napredna podešavanja</AccordionSummary>
                <AccordionDetails>
                  <Stack gap={2}>
                    {["HTTP", "API", "PORTAL"].includes(form.method) && (
                      <>
                        <TextField select label="Metod" value={form.http_method} onChange={(event) => update("http_method", event.target.value)}>
                          <MenuItem value="GET">GET</MenuItem><MenuItem value="POST">POST</MenuItem>
                        </TextField>
                        <TextField multiline minRows={2} label="Javni parametri" value={form.public_query} helperText="Jedan parametar po redu: naziv=vrednost. Ne unosite lozinke." onChange={(event) => update("public_query", event.target.value)} />
                        <TextField multiline minRows={2} label="Javna zaglavlja" value={form.public_headers} helperText="Jedno zaglavlje po redu: naziv=vrednost." onChange={(event) => update("public_headers", event.target.value)} />
                        {form.method === "PORTAL" && (
                          <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography fontWeight={700} mb={0.5}>
                              Tehnički nazivi login polja
                            </Typography>
                            <Typography variant="body2" color="text.secondary" mb={2}>
                              Ovo nisu dodatni pristupni podaci. Menjaju se samo
                              kada portal koristi drugačije HTML nazive polja.
                              Za EPI Computers unesite „user“ i „pass“.
                            </Typography>
                            <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                              <TextField
                                fullWidth
                                label="HTML polje korisničkog imena"
                                required
                                value={form.username_field}
                                helperText="Najčešće: username ili user."
                                onChange={(event) => update("username_field", event.target.value)}
                              />
                              <TextField
                                fullWidth
                                label="HTML polje lozinke"
                                required
                                value={form.password_field}
                                helperText="Najčešće: password ili pass."
                                onChange={(event) => update("password_field", event.target.value)}
                              />
                            </Stack>
                            <Stack gap={2} mt={2}>
                              <TextField
                                label="URL za slanje prijave (opciono)"
                                value={form.login_submit_url}
                                helperText="Ostavite prazno da sistem automatski koristi action iz login forme."
                                onChange={(event) => update("login_submit_url", event.target.value)}
                              />
                              <TextField
                                multiline
                                minRows={2}
                                label="Dodatna javna polja login forme"
                                value={form.login_form_fields}
                                helperText="Samo netajna polja, jedno po redu: naziv=vrednost. Hidden/CSRF polja sistem preuzima automatski."
                                onChange={(event) => update("login_form_fields", event.target.value)}
                              />
                            </Stack>
                          </Paper>
                        )}
                      </>
                    )}
                    <TextField label="Maksimalno čekanje (sekunde)" value={form.timeout} onChange={(event) => update("timeout", event.target.value)} />
                    <FormControlLabel control={<Checkbox checked={form.verify_tls} onChange={(event) => update("verify_tls", event.target.checked)} />} label="Proveri bezbednosni sertifikat" />
                  </Stack>
                </AccordionDetails>
              </Accordion>
              <TextField multiline minRows={2} label="Opis" value={form.description} onChange={(event) => update("description", event.target.value)} />
              {!networkSupported && form.method !== "MANUAL_UPLOAD" && (
                <Alert severity="info">
                  Automatsko preuzimanje za ovaj tip izvora biće dostupno u narednoj fazi razvoja. Podešavanja možete sačuvati kao nacrt.
                </Alert>
              )}
            </Stack>
          )}
          {step === 2 && probe && (
            <Stack gap={2}>
              <Alert severity={probe.successful ? "success" : "error"}>{probe.message}</Alert>
              <Grid container spacing={1}>
                {probe.steps.map((item) => (
                  <Grid item xs={12} sm={6} key={item.label}>
                    <Stack direction="row" gap={1} alignItems="center">
                      {item.successful ? (
                        <CheckCircleRounded color="success" />
                      ) : (
                        <CancelRounded color="error" />
                      )}
                      <Typography>{item.label}</Typography>
                    </Stack>
                  </Grid>
                ))}
              </Grid>
              <Typography>Format: {probe.detected_format ?? "nije prepoznat"}</Typography>
              <Typography>Veličina: {probe.size_bytes.toLocaleString("sr-RS")} bajtova</Typography>
              <Typography>Pronađeni zapisi: {probe.approximate_record_count ?? "—"}</Typography>
              {probe.preview.length > 0 && (
                <Box sx={{ overflowX: "auto" }}>
                  <Typography variant="h6" mb={1}>Pregled prvih zapisa</Typography>
                  <Stack gap={1}>
                    {probe.preview.map((row, index) => (
                      <Paper key={index} variant="outlined" sx={{ p: 1.5 }}>
                        <Typography variant="caption" color="text.secondary">
                          Zapis {index + 1}
                        </Typography>
                        <Grid container spacing={1} mt={0.25}>
                          {Object.entries(row).map(([key, value]) => (
                            <Grid item xs={12} sm={6} md={4} key={key}>
                              <Typography variant="caption" color="text.secondary">
                                {key}
                              </Typography>
                              <Typography sx={{ overflowWrap: "anywhere" }}>
                                {value == null ? "—" : String(value)}
                              </Typography>
                            </Grid>
                          ))}
                        </Grid>
                      </Paper>
                    ))}
                  </Stack>
                </Box>
              )}
              <Accordion>
                <AccordionSummary>Tehnički detalji</AccordionSummary>
                <AccordionDetails>
                  <Typography>HTTP status: {probe.http_status ?? "—"}</Typography>
                  <Typography>Content type: {probe.content_type ?? "—"}</Typography>
                  <Typography>Trajanje: {probe.duration_ms} ms</Typography>
                  <Typography>Checksum: {probe.checksum ?? "—"}</Typography>
                </AccordionDetails>
              </Accordion>
            </Stack>
          )}
          {step === 3 && (
            <Alert severity="success">
              Konekcija je aktivna. Sledeći koraci su podešavanje Schema i Mapping profila.
            </Alert>
          )}
        </DialogContent>
        <Divider />
        <DialogActions>
          <Button onClick={() => setWizardOpen(false)}>Zatvori</Button>
          {step === 0 && <Button variant="contained" onClick={() => setStep(1)}>Nastavi</Button>}
          {step === 1 && (
            <>
              <Button onClick={() => saveDraft.mutate()} disabled={!form.name.trim() || !portalReady || saveDraft.isPending}>Sačuvaj kao nacrt</Button>
              {networkSupported || form.method === "MANUAL_UPLOAD" ? (
                <Button
                  variant="contained"
                  startIcon={<CloudDownloadRounded />}
                  onClick={() => testConnection.mutate()}
                  disabled={
                    !form.name.trim() ||
                    !portalReady ||
                    !certificateReady ||
                    testConnection.isPending ||
                    (form.method === "MANUAL_UPLOAD" && !probeFile)
                  }
                >
                  {form.method === "MANUAL_UPLOAD" ? "Probno učitaj fajl" : "Probno preuzmi cenovnik"}
                </Button>
              ) : (
                <Button variant="contained" onClick={() => saveDraft.mutate()} disabled={!form.name.trim()}>Sačuvaj nacrt</Button>
              )}
            </>
          )}
          {step === 2 && draft && (
            <Button variant="contained" disabled={!probe?.successful || activate.isPending} onClick={() => activate.mutate(draft)}>
              Aktiviraj konekciju
            </Button>
          )}
        </DialogActions>
      </Dialog>
      <Dialog open={credentialsOpen} onClose={() => setCredentialsOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Promeni pristupne podatke</DialogTitle>
        <DialogContent>
          <Stack gap={2} mt={1}>
            <TextField select label="Način prijave" value={form.authentication_type} onChange={(event) => selectAuthenticationType(event.target.value)}>
              <MenuItem value="BASIC">Korisničko ime i lozinka</MenuItem>
              <MenuItem value="BEARER">Bearer token</MenuItem>
              <MenuItem value="API_KEY">API ključ</MenuItem>
              <MenuItem value="CLIENT_CERTIFICATE">Klijentski sertifikat (mTLS)</MenuItem>
              <MenuItem value="SOAP_BODY">SOAP servis (CT / PIN-ALSO)</MenuItem>
            </TextField>
            {form.integration_profile !== "ASBIS_IT4PROFIT" && !(["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(form.authentication_type)) && <TextField select label="Gde dobavljač očekuje pristupne podatke" value={form.placement} onChange={(event) => update("placement", event.target.value)}>
              <MenuItem value="HEADER">Bezbednosno zaglavlje</MenuItem>
              <MenuItem value="QUERY">Parametri adrese</MenuItem>
            </TextField>}
            {form.integration_profile === "ASBIS_IT4PROFIT" && (
              <Alert severity="info">ASBIS API koristi fiksne URL parametre USERNAME i PASSWORD.</Alert>
            )}
            {(form.authentication_type === "BASIC" ||
              (form.authentication_type === "SOAP_BODY" &&
                form.integration_profile === "CT_SOAP")) && (
              <>
                <TextField label="Korisničko ime" value={form.username} onChange={(event) => update("username", event.target.value)} />
                <TextField type="password" label="Lozinka" value={form.password} onChange={(event) => update("password", event.target.value)} />
              </>
            )}
            {form.authentication_type === "BEARER" && (
              <TextField type="password" label="Token" value={form.token} onChange={(event) => update("token", event.target.value)} />
            )}
            {form.authentication_type === "API_KEY" && (
              <TextField type="password" label="API ključ" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} />
            )}
            {form.integration_profile === "ASBIS_IT4PROFIT" && (
              <>
                <Alert severity="info">API i email lozinke čuvaju se zajedno u postojećem zaštićenom fajlu, van baze.</Alert>
                <TextField label="IMAP korisničko ime" value={form.imap_username} onChange={(event) => update("imap_username", event.target.value)} />
                <TextField type="password" label="IMAP lozinka" value={form.imap_password} onChange={(event) => update("imap_password", event.target.value)} />
              </>
            )}
            {form.authentication_type === "SOAP_BODY" && form.integration_profile === "PIN_SOAP" && (
              <>
                <TextField type="password" label="Klijentski kod (GUID)" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} />
                <TextField label="Shop ID" value={form.pin_shop_id} onChange={(event) => update("pin_shop_id", event.target.value)} helperText="Podrazumevana vrednost je 4." />
              </>
            )}
            {!(["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(form.authentication_type)) && form.placement === "QUERY" && (
              <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
                <TextField
                  fullWidth
                  label="Naziv parametra korisničkog imena"
                  value={form.username_parameter}
                  onChange={(event) => update("username_parameter", event.target.value)}
                />
                <TextField
                  fullWidth
                  label="Naziv parametra lozinke"
                  value={form.password_parameter}
                  onChange={(event) => update("password_parameter", event.target.value)}
                />
              </Stack>
            )}
            {form.authentication_type === "CLIENT_CERTIFICATE" && (
              <>
                <Alert severity="info">Novi sertifikat će zameniti postojeći tek nakon uspešne provere fajla i lozinke.</Alert>
                <Button component="label" variant="outlined">
                  {certificateFile ? certificateFile.name : "Izaberi novi .p12 / .pfx sertifikat"}
                  <input hidden type="file" accept=".p12,.pfx,application/x-pkcs12" onChange={(event) => setCertificateFile(event.target.files?.[0] ?? null)} />
                </Button>
                <TextField type="password" label="Lozinka sertifikata" value={form.certificate_password} onChange={(event) => update("certificate_password", event.target.value)} />
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCredentialsOpen(false)}>Otkaži</Button>
          <Button variant="contained" onClick={() => changeCredentials.mutate()} disabled={changeCredentials.isPending}>
            Sačuvaj pristupne podatke
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
