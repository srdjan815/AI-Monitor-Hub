import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddRounded,
  ArchiveRounded,
  CheckCircleRounded,
  CloudDownloadRounded,
  KeyRounded,
  LinkRounded
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
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useAuth } from "../state/AuthContext";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Source, SourceProbeResult } from "../types";

const methods = [
  ["HTTP", "Direktan URL", "Cenovnik je dostupan preko stabilne internet adrese."],
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
  http_method: "GET",
  login_required: false,
  placement: "HEADER",
  authentication_type: "NONE",
  username: "",
  password: "",
  token: "",
  api_key: "",
  username_parameter: "username",
  password_parameter: "password",
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
  if (form.method === "HTTP" && form.login_required) {
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
      verify_tls: form.verify_tls
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

export function SourcesPage() {
  const workspace = useWorkspace();
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Source | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(initialForm);
  const [draft, setDraft] = useState<Source | null>(null);
  const [probe, setProbe] = useState<SourceProbeResult | null>(null);
  const [probeFile, setProbeFile] = useState<File | null>(null);
  const [credentialsOpen, setCredentialsOpen] = useState(false);

  const sources = useQuery({
    queryKey: ["sources", workspace.supplierId, page],
    queryFn: () =>
      supplierApi.sources(workspace.supplierId, {
        limit: 25,
        offset: page * 25,
        active_only: false
      }),
    enabled: Boolean(workspace.supplierId),
    placeholderData: (previous) => previous
  });

  const saveDraft = useMutation({
    mutationFn: async () => {
      const source = draft
        ? await supplierApi.updateSource(workspace.supplierId, draft.id, {
            ...sourcePayload(form),
            source_type: undefined,
            version: draft.version
          })
        : await supplierApi.createSource(workspace.supplierId, sourcePayload(form));
      const hasCredential =
        form.password || form.token || form.api_key;
      if (hasCredential) {
        await supplierApi.writeSourceCredentials(workspace.supplierId, source.id, {
          placement: form.placement,
          username: form.username || null,
          password: form.password || null,
          token: form.token || null,
          api_key: form.api_key || null,
          username_parameter: form.username_parameter,
          password_parameter: form.password_parameter
        });
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
  const changeCredentials = useMutation({
    mutationFn: async () => {
      if (!opened) throw new Error("Konekcija nije izabrana");
      return supplierApi.writeSourceCredentials(opened.supplier_id, opened.id, {
        placement: form.placement,
        username: form.username || null,
        password: form.password || null,
        token: form.token || null,
        api_key: form.api_key || null,
        username_parameter: form.username_parameter,
        password_parameter: form.password_parameter
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
    []
  );

  const update = (key: keyof ConnectionForm, value: string | boolean) =>
    setForm((current) => ({ ...current, [key]: value }));
  const networkSupported = ["HTTP", "API"].includes(form.method);

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
                startIcon={<CloudDownloadRounded />}
                onClick={async () => {
                  const result = await supplierApi.probeSource(opened.supplier_id, opened.id);
                  setProbe(result);
                  if (result.successful) toast.success(result.message);
                  else toast.error(result.message);
                }}
              >
                Probno preuzmi
              </Button>
              <Button
                startIcon={<KeyRounded />}
                onClick={() => {
                  setForm((current) => ({
                    ...current,
                    username: "",
                    password: "",
                    token: "",
                    api_key: ""
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
              <Typography variant="h6">Spremnost procesa</Typography>
              <Stack gap={1} mt={1}>
                <Typography>
                  Konekcija: {
                    opened.has_secret_reference && !opened.credentials_available
                      ? "nedostaju pristupni podaci"
                      : opened.last_validation_status === "VALID"
                        ? "spremna"
                        : "potrebna provera"
                  }
                </Typography>
                <Typography>Schema: proverite na stranici Schema profili</Typography>
                <Typography>Mapping: proverite na stranici Mapping profili</Typography>
                <Typography>Acquisition: spreman nakon Schema i Mapping podešavanja</Typography>
              </Stack>
              <Stack direction="row" gap={1} mt={2}>
                <Button href="/schemas">Podesi Schema Profile</Button>
                <Button href="/mappings">Podesi Mapping Profile</Button>
                <Button href="/acquisitions">Otvori Acquisition</Button>
              </Stack>
            </Paper>
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
                  <Card variant={form.method === value ? "elevation" : "outlined"}>
                    <CardActionArea onClick={() => update("method", value)}>
                      <CardContent>
                        <Typography variant="h6">{title}</Typography>
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
              {["HTTP", "API", "MANUAL_UPLOAD"].includes(form.method) && (
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
              {["HTTP", "API"].includes(form.method) && (
                <>
                  <TextField
                    label={form.method === "API" ? "Osnovni URL" : "URL za preuzimanje"}
                    required
                    value={form.url}
                    helperText="Adresa sa koje sistem preuzima cenovnik."
                    onChange={(event) => update("url", event.target.value)}
                  />
                  {form.method === "API" && (
                    <TextField
                      label="Endpoint"
                      value={form.endpoint}
                      helperText="Putanja API operacije, na primer /v1/products."
                      onChange={(event) => update("endpoint", event.target.value)}
                    />
                  )}
                  <FormControlLabel
                    control={<Switch checked={form.login_required || form.method === "API"} onChange={(event) => update("login_required", event.target.checked)} disabled={form.method === "API"} />}
                    label="Potrebna je prijava"
                  />
                  {(form.login_required || form.method === "API") && (
                    <>
                      <TextField
                        select
                        label="Način prijave"
                        value={form.authentication_type}
                        onChange={(event) => update("authentication_type", event.target.value)}
                      >
                        <MenuItem value="NONE">Bez prijave</MenuItem>
                        <MenuItem value="BASIC">Korisničko ime i lozinka</MenuItem>
                        <MenuItem value="BEARER">Bearer token</MenuItem>
                        <MenuItem value="API_KEY">API ključ</MenuItem>
                      </TextField>
                      <TextField select label="Gde dobavljač očekuje podatke za prijavu" value={form.placement} onChange={(event) => update("placement", event.target.value)}>
                        <MenuItem value="HEADER">Bezbednosno zaglavlje</MenuItem>
                        <MenuItem value="QUERY">Parametri adrese (npr. DS Computers)</MenuItem>
                      </TextField>
                      {["BASIC", "API_KEY"].includes(form.authentication_type) && (
                        <TextField label="Korisničko ime" value={form.username} onChange={(event) => update("username", event.target.value)} />
                      )}
                      {form.authentication_type === "BASIC" && (
                        <TextField type="password" label="Lozinka" value={form.password} onChange={(event) => update("password", event.target.value)} />
                      )}
                      {form.authentication_type === "BEARER" && (
                        <TextField type="password" label="Token" value={form.token} onChange={(event) => update("token", event.target.value)} />
                      )}
                      {form.authentication_type === "API_KEY" && (
                        <TextField type="password" label="API ključ ili lozinka" value={form.api_key} onChange={(event) => update("api_key", event.target.value)} />
                      )}
                      {form.placement === "QUERY" && (
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
                    {["HTTP", "API"].includes(form.method) && (
                      <>
                        <TextField select label="Metod" value={form.http_method} onChange={(event) => update("http_method", event.target.value)}>
                          <MenuItem value="GET">GET</MenuItem><MenuItem value="POST">POST</MenuItem>
                        </TextField>
                        <TextField multiline minRows={2} label="Javni parametri" value={form.public_query} helperText="Jedan parametar po redu: naziv=vrednost. Ne unosite lozinke." onChange={(event) => update("public_query", event.target.value)} />
                        <TextField multiline minRows={2} label="Javna zaglavlja" value={form.public_headers} helperText="Jedno zaglavlje po redu: naziv=vrednost." onChange={(event) => update("public_headers", event.target.value)} />
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
                      <CheckCircleRounded color={item.successful ? "success" : "disabled"} />
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
              <Button onClick={() => saveDraft.mutate()} disabled={!form.name.trim() || saveDraft.isPending}>Sačuvaj kao nacrt</Button>
              {networkSupported || form.method === "MANUAL_UPLOAD" ? (
                <Button
                  variant="contained"
                  startIcon={<CloudDownloadRounded />}
                  onClick={() => testConnection.mutate()}
                  disabled={
                    !form.name.trim() ||
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
            <TextField select label="Način prijave" value={form.authentication_type} onChange={(event) => update("authentication_type", event.target.value)}>
              <MenuItem value="BASIC">Korisničko ime i lozinka</MenuItem>
              <MenuItem value="BEARER">Bearer token</MenuItem>
              <MenuItem value="API_KEY">API ključ</MenuItem>
            </TextField>
            <TextField select label="Gde dobavljač očekuje pristupne podatke" value={form.placement} onChange={(event) => update("placement", event.target.value)}>
              <MenuItem value="HEADER">Bezbednosno zaglavlje</MenuItem>
              <MenuItem value="QUERY">Parametri adrese</MenuItem>
            </TextField>
            {form.authentication_type === "BASIC" && (
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
