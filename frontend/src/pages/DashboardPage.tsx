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
  const failurePages: Record<string, string> = {
    acquisition: "/acquisitions",
    snapshot: "/snapshots",
    delta: "/deltas"
  };
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
      <Grid container spacing={1.25}>
        {cards.map(([title, value, icon, caption, tone]) => (
          <Grid item xs={6} sm={4} lg={2} key={title}>
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
          <Paper sx={{ p: { xs: 1.25, md: 1.5 }, overflow: "hidden" }}>
            <Typography variant="h2">Stanje cenovnika dobavljača</Typography>
            <Typography color="text.secondary" variant="caption" mt={0.25} mb={1} display="block">
              Odvojeni pregled konekcije, pripreme podataka i poslednje obrade.
            </Typography>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: {
                  xs: "1fr",
                  lg: "repeat(2, minmax(0, 1fr))"
                },
                gap: 1
              }}
            >
              {metrics.data?.supplier_processes.map((item) => (
                <Paper
                  key={item.supplier_id}
                  variant="outlined"
                  sx={{
                    p: 1.25,
                    minWidth: 0,
                    overflow: "hidden",
                    bgcolor: "background.default"
                  }}
                >
                  <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    gap={1.5}
                    mb={1}
                  >
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={750} noWrap title={item.supplier_name}>
                        {item.supplier_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" noWrap display="block">
                        {item.source_format ?? "Cenovnik nije povezan"}
                      </Typography>
                    </Box>
                    <Typography
                      variant="body2"
                      fontWeight={750}
                      noWrap
                      sx={{ flexShrink: 0 }}
                    >
                      {item.article_count == null
                        ? "Nema proizvoda"
                        : `${item.article_count.toLocaleString("sr-RS")} proizvoda`}
                    </Typography>
                  </Stack>
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: {
                        xs: "repeat(2, minmax(0, 1fr))",
                        sm: "repeat(4, minmax(76px, 1fr))"
                      },
                      gap: 0.75
                    }}
                  >
                    {[
                      ["Konekcija", item.connection_status],
                      ["Schema", item.schema_status],
                      ["Mapping", item.mapping_status],
                      ["Acquisition", item.acquisition_status]
                    ].map(([label, status]) => (
                      <Box
                        key={label}
                        sx={{
                          minWidth: 0,
                          p: 0.75,
                          borderRadius: 1,
                          bgcolor: "background.paper",
                          border: 1,
                          borderColor: "divider"
                        }}
                      >
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                          sx={{ fontSize: "0.66rem", mb: 0.4 }}
                        >
                          {label}
                        </Typography>
                        <Box sx={{ "& .MuiChip-root": { maxWidth: "100%" } }}>
                          <StatusChip value={status === "Radi" || status === "Spremno" ? "READY" : status === "Ne radi" ? "FAILED" : "PENDING"} />
                        </Box>
                      </Box>
                    ))}
                  </Box>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                    mt={0.85}
                    noWrap
                    title={
                      item.last_success_at
                        ? `Preuzeto ${new Date(item.last_success_at).toLocaleString("sr-RS")}`
                        : "Poslednje preuzimanje nije dostupno"
                    }
                  >
                    {item.last_success_at
                      ? `Preuzeto ${new Date(item.last_success_at).toLocaleString("sr-RS")}`
                      : "Poslednje preuzimanje nije dostupno"}
                  </Typography>
                    {item.warning && (
                      <Typography
                        variant="caption"
                        color="warning.main"
                        display="block"
                        mt={0.5}
                        sx={{ lineHeight: 1.2 }}
                      >
                        {item.warning}
                      </Typography>
                    )}
                </Paper>
              ))}
              {!metrics.data?.supplier_processes.length && (
                <Typography color="text.secondary">Nema aktivnih dobavljača.</Typography>
              )}
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 1.5, minHeight: 220 }}>
            <Typography variant="h2">Nedavna aktivnost</Typography>
            <Typography color="text.secondary" variant="caption" mt={0.25} display="block">
              Poslednji Acquisition, Snapshot i Delta događaji.
            </Typography>
            {activity.isLoading ? <Box mt={1}><LoadingBlock /></Box> : activity.isError ? (
              <Box mt={1}><ErrorBlock error={activity.error} retry={() => activity.refetch()} /></Box>
            ) : (
              <List dense disablePadding sx={{ mt: 0.5 }}>
                {activity.data?.latest_operations.slice(0, 7).map((item) => (
                  <ListItem
                    key={`${item.resource_type}-${item.id}`}
                    disableGutters
                    sx={{ py: 0.35, minHeight: 38 }}
                  >
                    <ListItemText
                      primary={item.code}
                      secondary={`${item.resource_type} · ${new Date(item.occurred_at).toLocaleString("sr-RS")}`}
                      primaryTypographyProps={{ variant: "body2", fontWeight: 650, lineHeight: 1.2 }}
                      secondaryTypographyProps={{ variant: "caption", lineHeight: 1.2 }}
                      sx={{ my: 0, minWidth: 0 }}
                    />
                    <StatusChip value={item.status} />
                  </ListItem>
                ))}
              </List>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Stack gap={1.5}>
            <Paper sx={{ p: 1.75 }}>
              <Typography variant="h2">Pažnja administratora</Typography>
              <Stack direction="row" alignItems="center" gap={1} mt={1.25} flexWrap="wrap">
                <StatusChip
                  value={(metrics.data?.active_incidents.value ?? 0) > 0 ? "ATTENTION" : "HEALTHY"}
                />
                <Typography>
                  {(metrics.data?.overdue_incidents.value ?? 0)} prekoračena incidenta
                </Typography>
              </Stack>
            </Paper>
            <Paper sx={{ p: 1.75 }}>
              <Typography variant="h2">Storage Health</Typography>
              <Stack direction="row" alignItems="center" gap={1} mt={1.25} flexWrap="wrap">
                <StatusChip value="ACTIVE" />
                <Typography>
                  {metrics.data?.archived_snapshots.value ?? 0} arhiviranih snapshot-a
                </Typography>
              </Stack>
            </Paper>
            <Paper sx={{ p: 1.75, overflow: "hidden" }}>
              <Typography variant="h2">Poslednji import</Typography>
              {failures.isError ? (
                <Alert severity="error" sx={{ mt: 2 }}>Widget nije dostupan; ostatak stranice radi.</Alert>
              ) : failures.data?.latest_acquisition ? (
                [failures.data.latest_acquisition].map((item) => (
                  <Box
                    key={item.id}
                    sx={{
                      mt: 1,
                      p: 1,
                      border: 1,
                      borderColor: "divider",
                      borderRadius: 1
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" gap={1}>
                      <Box minWidth={0}>
                        <Typography variant="body2" fontWeight={700}>
                          {item.status === "FAILED"
                            ? "Import nije uspeo"
                            : item.status === "PARTIALLY_SUCCEEDED"
                              ? "Import je delimično uspeo"
                              : "Import je završen"}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {[item.supplier_name, item.source_name].filter(Boolean).join(" · ") ||
                            "Dobavljač nije dostupan"}
                        </Typography>
                      </Box>
                      <StatusChip value={item.status} />
                    </Stack>
                    <Typography variant="body2" mt={0.5}>
                      {item.failure_message ||
                        (item.status === "SUCCEEDED"
                          ? "Poslednji cenovnik je uspešno obrađen."
                          : item.status === "PARTIALLY_SUCCEEDED"
                            ? "Ispravni artikli su obrađeni; deo zapisa je odbijen."
                            : "Obrada je završena bez dodatne poruke.")}
                    </Typography>
                    <Stack
                      direction={{ xs: "column", sm: "row" }}
                      justifyContent="space-between"
                      alignItems={{ xs: "flex-start", sm: "center" }}
                      gap={0.5}
                      mt={0.5}
                    >
                      <Typography variant="caption" color="text.secondary">
                        {item.code}
                        {item.error_count ? ` · ${item.error_count} grešaka` : ""}
                        {` · ${new Date(item.occurred_at).toLocaleString("sr-RS")}`}
                      </Typography>
                      <Button
                        component={Link}
                        to={failurePages[item.resource_type] ?? "/dashboard"}
                        size="small"
                        sx={{ minWidth: 0, p: 0 }}
                      >
                        Otvori detalje
                      </Button>
                    </Stack>
                  </Box>
                ))
              ) : (
                <Typography color="text.secondary" mt={2}>
                  Još nije pokrenut nijedan import cenovnika.
                </Typography>
              )}
            </Paper>
          </Stack>
        </Grid>
      </Grid>
    </>
  );
}
