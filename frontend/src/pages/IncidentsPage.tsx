import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AssignmentIndRounded,
  CheckCircleRounded,
  CommentRounded,
  DoneAllRounded,
  FlagRounded,
  PauseCircleRounded,
  PlayArrowRounded,
  ReplayRounded
} from "@mui/icons-material";
import {
  Box,
  Button,
  Divider,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { LoadingBlock } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { RecordDetails } from "../components/RecordDetails";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../state/AuthContext";
import type { ApiError, Operation } from "../types";

export function IncidentsPage() {
  const auth = useAuth();
  const client = useQueryClient();
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Operation | null>(null);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [assignee, setAssignee] = useState("");
  const [priority, setPriority] = useState("P3");
  const [comment, setComment] = useState("");
  const incidents = useQuery({
    queryKey: ["incidents", page, status, query],
    queryFn: () =>
      supplierApi.incidents({
        limit: 25,
        offset: page * 25,
        status: status || undefined,
        query: query || undefined,
        sort_by: "created_at",
        sort_order: "desc"
      }),
    placeholderData: (previous) => previous
  });
  const details = useQuery({
    queryKey: ["incident-detail", opened?.id],
    queryFn: () => supplierApi.incidentDetail(opened!.id),
    enabled: Boolean(opened)
  });
  const events = useQuery({
    queryKey: ["incident-events", opened?.id],
    queryFn: () => supplierApi.incidentEvents(opened!.id),
    enabled: Boolean(opened)
  });
  const comments = useQuery({
    queryKey: ["incident-comments", opened?.id],
    queryFn: () => supplierApi.incidentComments(opened!.id),
    enabled: Boolean(opened)
  });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["incidents"] });
    client.invalidateQueries({ queryKey: ["incident-detail"] });
    client.invalidateQueries({ queryKey: ["incident-events"] });
    client.invalidateQueries({ queryKey: ["incident-comments"] });
  };
  const action = useMutation({
    mutationFn: ({ name, body }: { name: string; body?: Record<string, unknown> }) =>
      supplierApi.incidentAction(opened!.id, name, body),
    onSuccess: (row) => {
      setOpened(row);
      toast.success("Incident je ažuriran.");
      refresh();
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const bulk = useMutation({
    mutationFn: (kind: "assign" | "priority") =>
      kind === "assign"
        ? supplierApi.bulkAssign(
            selected.map((incident_id) => ({ incident_id, assigned_user_id: assignee }))
          )
        : supplierApi.bulkPriority(
            selected.map((incident_id) => ({ incident_id, priority }))
          ),
    onSuccess: (result) => {
      toast.success(`${result.succeeded_count} uspešno, ${result.failed_count} neuspešno.`);
      setSelected([]);
      refresh();
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const columns = useMemo<Column<Operation>[]>(
    () => [
      {
        key: "incident_code",
        label: "Incident",
        tooltip: "Stabilna Incident šifra.",
        sortable: true,
        render: (row) => <Typography fontFamily="monospace">{String(row.incident_code)}</Typography>,
        csv: (row) => String(row.incident_code)
      },
      {
        key: "title",
        label: "Naslov",
        tooltip: "Kratak bezbedan opis problema.",
        width: 280,
        render: (row) => <Typography fontWeight={650}>{String(row.title)}</Typography>,
        csv: (row) => String(row.title)
      },
      {
        key: "status",
        label: "Status",
        tooltip: "Trenutna workflow faza.",
        sortable: true,
        render: (row) => <StatusChip value={row.status} />,
        csv: (row) => row.status
      },
      {
        key: "priority",
        label: "Prioritet",
        tooltip: "Operativna hitnost; nije isto što i severity.",
        sortable: true,
        render: (row) => <StatusChip value={String(row.priority)} />,
        csv: (row) => String(row.priority)
      },
      {
        key: "severity",
        label: "Severity",
        tooltip: "Težina koju određuje backend detekcija ili pravilo.",
        render: (row) => <StatusChip value={String(row.severity)} />,
        csv: (row) => String(row.severity)
      },
      {
        key: "assigned_user_id",
        label: "Dodeljeno",
        tooltip: "Foundation subject operatera.",
        render: (row) => String(row.assigned_user_id ?? "Nedodeljeno"),
        csv: (row) => String(row.assigned_user_id ?? "")
      }
    ],
    []
  );
  const workflow = details.data ?? opened;
  const incidentContext =
    workflow?.sanitized_context && typeof workflow.sanitized_context === "object"
      ? (workflow.sanitized_context as Record<string, unknown>)
      : undefined;
  return (
    <>
      <PageHeader
        title="Incident Center"
        description="Jedinstven operativni ekran za trijažu, dodelu, istragu i resolution."
      />
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h2" mb={1}>Redosled rada sa cenovnikom</Typography>
        <Typography color="text.secondary">
          1. Dobavljači: proverite osnovne podatke. 2. Izvori: preuzmite i testirajte
          konekciju. 3. Analiza cenovnika: proverite pronađena polja. 4. Mapiranje polja:
          mapirajte obavezna polja i testirajte mapiranje. 5. Import cenovnika: pregledajte
          prihvaćene i odbijene artikle. 6. Snapshots: kreirajte validno stanje iz poslednjeg
          uspešnog importa. 7. Delta Runs: proverite promene prema prethodnom stanju. Ako
          faza ne prođe, prvo otvorite njen incident i pratite preporučeni sledeći korak.
        </Typography>
      </Paper>
      <Stack direction={{ xs: "column", md: "row" }} gap={1.5} mb={2}>
        <TextField
          size="small"
          label="Pretraga po šifri ili naslovu"
          value={query}
          onChange={(event) => { setQuery(event.target.value); setPage(0); }}
          sx={{ minWidth: 280 }}
        />
        <TextField
          select
          size="small"
          label="Status"
          value={status}
          onChange={(event) => { setStatus(event.target.value); setPage(0); }}
          sx={{ minWidth: 190 }}
        >
          <MenuItem value="">Svi statusi</MenuItem>
          {["OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED", "DISMISSED", "SUPPRESSED"].map((value) => (
            <MenuItem key={value} value={value}>{value}</MenuItem>
          ))}
        </TextField>
      </Stack>
      <EntityTable
        tableId="incidents"
        columns={columns}
        rows={incidents.data?.items ?? []}
        total={incidents.data?.total ?? 0}
        page={page}
        pageSize={25}
        loading={incidents.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={setOpened}
        onRefresh={() => incidents.refetch()}
        bulkActions={
          <Stack direction="row" gap={1} alignItems="center">
            {auth.can("incidents.assign") && (
              <>
                <TextField size="small" label="Operater" value={assignee} onChange={(event) => setAssignee(event.target.value)} />
                <Button disabled={!assignee} onClick={() => bulk.mutate("assign")}>Dodeli</Button>
              </>
            )}
            {auth.can("incidents.manage") && (
              <>
                <TextField select size="small" value={priority} onChange={(event) => setPriority(event.target.value)}>
                  {["P1", "P2", "P3", "P4"].map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                </TextField>
                <Button onClick={() => bulk.mutate("priority")}>Prioritet</Button>
              </>
            )}
          </Stack>
        }
      />
      <DetailDrawer
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={String(workflow?.title ?? "")}
        subtitle={String(workflow?.incident_code ?? "")}
        actions={
          workflow ? (
            <>
              {workflow.status === "OPEN" && auth.can("incidents.acknowledge") && (
                <Button startIcon={<CheckCircleRounded />} onClick={() => action.mutate({ name: "acknowledge" })}>Potvrdi</Button>
              )}
              {["OPEN", "ACKNOWLEDGED"].includes(workflow.status) && auth.can("incidents.manage") && (
                <Button startIcon={<PlayArrowRounded />} onClick={() => action.mutate({ name: "start" })}>Pokreni istragu</Button>
              )}
              {auth.can("incidents.assign") && (
                <Tooltip title="Dodeli Incident Foundation subject identitetu.">
                  <Button
                    startIcon={<AssignmentIndRounded />}
                    onClick={() => {
                      const value = prompt("Foundation subject operatera", assignee);
                      if (value) action.mutate({ name: "assign", body: { assigned_user_id: value } });
                    }}
                  >
                    Dodeli
                  </Button>
                </Tooltip>
              )}
              {auth.can("incidents.resolve") && !["RESOLVED", "DISMISSED"].includes(workflow.status) && (
                <Button
                  startIcon={<DoneAllRounded />}
                  onClick={() => action.mutate({ name: "resolve", body: { resolution_code: "ADMIN_CONFIRMED", resolution_summary: "Rešeno kroz Supplier Admin UI" } })}
                >
                  Reši
                </Button>
              )}
              {auth.can("incidents.suppress") && workflow.status !== "SUPPRESSED" && (
                <Button startIcon={<PauseCircleRounded />} onClick={() => action.mutate({ name: "suppress", body: { reason: "Potisnuto kroz Supplier Admin UI" } })}>Suppress</Button>
              )}
              {auth.can("incidents.suppress") && ["RESOLVED", "DISMISSED", "SUPPRESSED"].includes(workflow.status) && (
                <Button startIcon={<ReplayRounded />} onClick={() => action.mutate({ name: "reopen" })}>Ponovo otvori</Button>
              )}
            </>
          ) : undefined
        }
      >
        {details.isLoading ? <LoadingBlock /> : workflow && (
          <Stack gap={3}>
            <RecordDetails record={workflow} exclude={["sanitized_context", "description"]} />
            {incidentContext && (
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="h2" mb={1}>Dijagnostika i sledeći korak</Typography>
                <Stack gap={0.75}>
                  {Boolean(incidentContext.pipeline_code) && (
                    <Typography>Pipeline: {String(incidentContext.pipeline_code)}</Typography>
                  )}
                  {Boolean(incidentContext.phase) && (
                    <Typography>Faza: {String(incidentContext.phase)}</Typography>
                  )}
                  {Boolean(incidentContext.failure_code) && (
                    <Typography>Razlog: {String(incidentContext.failure_code)}</Typography>
                  )}
                  {Boolean(incidentContext.recommended_action) && (
                    <Typography fontWeight={650}>
                      Sledeći korak: {String(incidentContext.recommended_action)}
                    </Typography>
                  )}
                  {Array.isArray(incidentContext.workflow) &&
                    incidentContext.workflow.map((step, index) => (
                      <Typography key={`${index}-${String(step)}`} color="text.secondary">
                        {index + 1}. {String(step)}
                      </Typography>
                    ))}
                </Stack>
              </Paper>
            )}
            <Divider />
            <Typography variant="h2">Komentari</Typography>
            <Stack direction="row" gap={1}>
              <TextField
                fullWidth
                size="small"
                label="Novi komentar"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                helperText="Plain text; backend sanitizuje sadržaj."
              />
              <Button
                startIcon={<CommentRounded />}
                disabled={!comment.trim() || !auth.can("incidents.comment")}
                onClick={() => {
                  action.mutate({ name: "comments", body: { body: comment } });
                  setComment("");
                }}
              >
                Dodaj
              </Button>
            </Stack>
            {comments.data?.items.map((item) => (
              <Paper key={item.id} variant="outlined" sx={{ p: 1.5 }}>
                <Typography>{String(item.body)}</Typography>
                <Typography variant="caption" color="text.secondary">{String(item.created_by)}</Typography>
              </Paper>
            ))}
            <Divider />
            <Typography variant="h2">Timeline</Typography>
            {events.data?.items.map((item) => (
              <Stack key={item.id} direction="row" gap={1.5} alignItems="center">
                <FlagRounded color="action" />
                <Box>
                  <Typography fontWeight={650}>{String(item.event_type)}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(item.created_at).toLocaleString("sr-RS")} · {String(item.actor_id)}
                  </Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        )}
      </DetailDrawer>
    </>
  );
}
