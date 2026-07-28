import {
  BusinessRounded,
  ErrorRounded,
  HubRounded,
  Inventory2Rounded,
  PlayCircleRounded,
  StorageRounded
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Grid,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import { Link } from "react-router-dom";
import { supplierApi } from "../api/supplierApi";
import { ErrorBlock, LoadingBlock } from "../components/AsyncState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";

export function DashboardPage() {
  const metrics = useQuery({
    queryKey: ["overview", "metrics"],
    queryFn: supplierApi.overview,
    refetchInterval: 60_000
  });
  const activity = useQuery({
    queryKey: ["overview", "activity"],
    queryFn: supplierApi.overview,
    refetchInterval: 60_000
  });
  const failures = useQuery({
    queryKey: ["overview", "failures"],
    queryFn: supplierApi.overview,
    refetchInterval: 30_000
  });
  const cards = [
    ["Aktivni dobavljači", metrics.data?.active_suppliers.value, <BusinessRounded />, "Broj aktivnih Supplier zapisa.", "primary"],
    ["Aktivni izvori", metrics.data?.active_source_connections.value, <HubRounded />, "Broj aktivnih Source Connection konfiguracija.", "primary"],
    ["Današnji Acquisitions", metrics.data?.recent_acquisitions.value, <PlayCircleRounded />, "Acquisition Run-ovi u izabranom periodu.", "success"],
    ["READY Snapshots", metrics.data?.ready_snapshots.value, <StorageRounded />, "Validni snapshot-i spremni za poređenje.", "success"],
    ["Aktivni incidenti", metrics.data?.active_incidents.value, <ErrorRounded />, "Otvoreni operativni incidenti.", "warning"],
    ["Neuspešni Acquisitions", metrics.data?.failed_acquisitions.value, <Inventory2Rounded />, "Neuspešna preuzimanja u periodu.", "error"]
  ] as const;
  return (
    <>
      <PageHeader
        title="Operativni pregled"
        description="Zdravlje dobavljačke platforme, pažnja i poslednje aktivnosti."
        actions={
          <>
            <Button component={Link} to="/sources" variant="outlined">Novi izvor</Button>
            <Button component={Link} to="/acquisitions" variant="contained">Pokreni Acquisition</Button>
          </>
        }
      />
      {metrics.isError && <ErrorBlock error={metrics.error} retry={() => metrics.refetch()} />}
      <Grid container spacing={2}>
        {cards.map(([title, value, icon, caption, tone]) => (
          <Grid item xs={12} sm={6} lg={4} key={title}>
            <MetricCard
              title={title}
              value={value}
              icon={icon}
              caption={caption}
              tone={tone}
              loading={metrics.isLoading}
            />
          </Grid>
        ))}
      </Grid>
      <Grid container spacing={2} mt={0}>
        <Grid item xs={12}>
          <Paper sx={{ p: 2.5 }}>
            <Typography variant="h2">Stanje cenovnika dobavljača</Typography>
            <Typography color="text.secondary" variant="body2" mt={0.5} mb={2}>
              Odvojeni pregled konekcije, pripreme podataka i poslednje obrade.
            </Typography>
            <Stack gap={1.5}>
              {metrics.data?.supplier_processes.map((item) => (
                <Paper key={item.supplier_id} variant="outlined" sx={{ p: 2 }}>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={3}>
                      <Typography fontWeight={750}>{item.supplier_name}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {item.source_format ?? "Cenovnik nije povezan"}
                      </Typography>
                    </Grid>
                    {[
                      ["Konekcija", item.connection_status],
                      ["Schema", item.schema_status],
                      ["Mapping", item.mapping_status],
                      ["Acquisition", item.acquisition_status]
                    ].map(([label, status]) => (
                      <Grid item xs={6} sm={3} md={1.5} key={label}>
                        <Typography variant="caption" color="text.secondary">{label}</Typography>
                        <Box mt={0.5}><StatusChip value={status === "Radi" || status === "Spremno" ? "READY" : status === "Ne radi" ? "FAILED" : "PENDING"} /></Box>
                        <Typography variant="caption">{status}</Typography>
                      </Grid>
                    ))}
                    <Grid item xs={12} md={3}>
                      <Typography fontWeight={700}>
                        {item.article_count == null
                          ? "Nema uspešnog preuzimanja"
                          : `${item.article_count.toLocaleString("sr-RS")} proizvoda`}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {item.last_success_at
                          ? `Preuzeto ${new Date(item.last_success_at).toLocaleString("sr-RS")}`
                          : "Poslednje preuzimanje nije dostupno"}
                      </Typography>
                      {item.warning && <Alert severity="warning" sx={{ mt: 1 }}>{item.warning}</Alert>}
                    </Grid>
                  </Grid>
                </Paper>
              ))}
              {!metrics.data?.supplier_processes.length && (
                <Typography color="text.secondary">Nema aktivnih dobavljača.</Typography>
              )}
            </Stack>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={7}>
          <Paper sx={{ p: 2.5, minHeight: 340 }}>
            <Typography variant="h2">Nedavna aktivnost</Typography>
            <Typography color="text.secondary" variant="body2" mt={0.5}>
              Poslednji Acquisition, Snapshot i Delta događaji.
            </Typography>
            {activity.isLoading ? <Box mt={2}><LoadingBlock /></Box> : activity.isError ? (
              <Box mt={2}><ErrorBlock error={activity.error} retry={() => activity.refetch()} /></Box>
            ) : (
              <List>
                {activity.data?.latest_operations.map((item) => (
                  <ListItem key={`${item.resource_type}-${item.id}`} disableGutters>
                    <ListItemText
                      primary={item.code}
                      secondary={`${item.resource_type} · ${new Date(item.occurred_at).toLocaleString("sr-RS")}`}
                    />
                    <StatusChip value={item.status} />
                  </ListItem>
                ))}
              </List>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} lg={5}>
          <Stack gap={2}>
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="h2">Pažnja administratora</Typography>
              <Stack direction="row" alignItems="center" gap={1} mt={2}>
                <StatusChip
                  value={(metrics.data?.active_incidents.value ?? 0) > 0 ? "ATTENTION" : "HEALTHY"}
                />
                <Typography>
                  {(metrics.data?.overdue_incidents.value ?? 0)} prekoračena incidenta
                </Typography>
              </Stack>
            </Paper>
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="h2">Storage Health</Typography>
              <Stack direction="row" alignItems="center" gap={1} mt={2}>
                <StatusChip value="ACTIVE" />
                <Typography>
                  {metrics.data?.archived_snapshots.value ?? 0} arhiviranih snapshot-a
                </Typography>
              </Stack>
            </Paper>
            <Paper sx={{ p: 2.5 }}>
              <Typography variant="h2">Nedavni kvarovi</Typography>
              {failures.isError ? (
                <Alert severity="error" sx={{ mt: 2 }}>Widget nije dostupan; ostatak stranice radi.</Alert>
              ) : failures.data?.recent_failures.length ? (
                failures.data.recent_failures.slice(0, 3).map((item) => (
                  <Stack key={item.id} direction="row" justifyContent="space-between" mt={1.5}>
                    <Typography>{item.code}</Typography><StatusChip value={item.status} />
                  </Stack>
                ))
              ) : (
                <Typography color="text.secondary" mt={2}>Nema nedavnih kvarova.</Typography>
              )}
            </Paper>
          </Stack>
        </Grid>
      </Grid>
    </>
  );
}
