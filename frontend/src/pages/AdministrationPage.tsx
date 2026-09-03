import { useQuery } from "@tanstack/react-query";
import { Paper, Stack, Typography } from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { LoadingBlock } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { RecordDetails } from "../components/RecordDetails";
import { StatusChip } from "../components/StatusChip";

export function AdministrationPage() {
  const rules = useQuery({
    queryKey: ["incident-rules"],
    queryFn: () =>
      supplierApi.nestedCollection(
        "/suppliers/platform/supplier-incident-rules",
        { limit: 100, offset: 0 }
      )
  });
  return (
    <>
      <PageHeader
        title="Administracija"
        description="Incident pravila, API ugovor, dozvole i operativna podešavanja."
      />
      <Paper sx={{ p: 2.5, mb: 2 }}>
        <Typography variant="h2">Incident Rules</Typography>
        <Typography color="text.secondary" mt={0.5}>
          Pravila samo konfigurišu postojeću detekciju; UI ne izračunava severity niti threshold odluke.
        </Typography>
      </Paper>
      {rules.isLoading ? <LoadingBlock /> : (
        <Stack gap={1.5}>
          {rules.data?.items.map((rule) => (
            <Paper key={rule.id} sx={{ p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography fontWeight={700}>{String(rule.name ?? rule.rule_code ?? rule.id)}</Typography>
                <StatusChip value={rule.enabled ? "ACTIVE" : "INACTIVE"} />
              </Stack>
              <RecordDetails record={rule} exclude={["threshold_configuration"]} />
            </Paper>
          ))}
        </Stack>
      )}
    </>
  );
}
