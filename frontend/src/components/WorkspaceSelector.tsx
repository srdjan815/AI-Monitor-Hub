import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Tooltip
} from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { useWorkspace } from "../state/WorkspaceContext";

export function WorkspaceSelector({ requireSource = true }: { requireSource?: boolean }) {
  const workspace = useWorkspace();
  const suppliers = useQuery({
    queryKey: ["workspace-suppliers"],
    queryFn: () => supplierApi.suppliers({ limit: 100, offset: 0, active_only: true })
  });
  const sources = useQuery({
    queryKey: ["workspace-sources", workspace.supplierId],
    queryFn: () =>
      supplierApi.sources(workspace.supplierId, {
        limit: 100,
        offset: 0,
        active_only: true
      }),
    enabled: Boolean(workspace.supplierId)
  });

  return (
    <Stack gap={1.5} mb={2}>
      {!workspace.supplierId && (
        <Alert severity="info">
          Izaberite dobavljača da biste otvorili njegov operativni radni prostor.
        </Alert>
      )}
      {requireSource && workspace.supplierId && !workspace.sourceId && (
        <Alert severity="info">
          Izaberite Source Connection za prikaz resursa.
        </Alert>
      )}
      <Stack direction={{ xs: "column", sm: "row" }} gap={1.5}>
        <Tooltip title="Dobavljač određuje vlasnika svih prikazanih resursa.">
          <FormControl size="small" sx={{ minWidth: 240 }}>
            <InputLabel id="workspace-supplier-label">Dobavljač</InputLabel>
            <Select
              labelId="workspace-supplier-label"
              label="Dobavljač"
              value={workspace.supplierId}
              onChange={(event) => workspace.setSupplierId(event.target.value)}
            >
              {suppliers.data?.items.map((supplier) => (
                <MenuItem key={supplier.id} value={supplier.id}>
                  {supplier.supplier_code} · {supplier.company_name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Tooltip>
        {requireSource && (
          <Tooltip title="Izvor određuje konfiguraciju, istoriju preuzimanja i snapshot tok.">
            <FormControl size="small" sx={{ minWidth: 240 }} disabled={!workspace.supplierId}>
              <InputLabel id="workspace-source-label">Source Connection</InputLabel>
              <Select
                labelId="workspace-source-label"
                label="Source Connection"
                value={workspace.sourceId}
                onChange={(event) => workspace.setSourceId(event.target.value)}
              >
                {sources.data?.items.map((source) => (
                  <MenuItem key={source.id} value={source.id}>
                    {source.source_code} · {source.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Tooltip>
        )}
      </Stack>
    </Stack>
  );
}
