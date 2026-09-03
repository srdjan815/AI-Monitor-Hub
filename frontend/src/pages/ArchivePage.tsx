import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArchiveRounded, RestoreRounded, VerifiedRounded } from "@mui/icons-material";
import { Button, Paper, Stack, Typography } from "@mui/material";
import { supplierApi } from "../api/supplierApi";
import { EmptyState, LoadingBlock } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import { useWorkspace } from "../state/WorkspaceContext";
import type { Operation } from "../types";

export function ArchivePage() {
  const workspace = useWorkspace();
  const [days, setDays] = useState(30);
  const candidates = useQuery({
    queryKey: ["archive-candidates", workspace.supplierId, days],
    queryFn: () =>
      supplierApi.nestedCollection<Operation>(
        `/suppliers/${workspace.supplierId}/snapshots/archive-candidates`,
        { older_than_days: days, limit: 100, offset: 0 }
      ),
    enabled: Boolean(workspace.supplierId)
  });
  return (
    <>
      <PageHeader
        title="Arhiva"
        description="Kandidati, verifikacija, export/offload i restore bez skrivene promene storage stanja."
      />
      <WorkspaceSelector requireSource={false} />
      <Stack direction="row" gap={1} mb={2}>
        {[30, 90, 180].map((value) => (
          <Button key={value} variant={days === value ? "contained" : "outlined"} onClick={() => setDays(value)}>
            Starije od {value} dana
          </Button>
        ))}
      </Stack>
      {candidates.isLoading ? <LoadingBlock /> : candidates.data?.items.length ? (
        <Stack gap={1.5}>
          {candidates.data.items.map((row) => (
            <Paper key={row.id} sx={{ p: 2 }}>
              <Stack direction={{ xs: "column", md: "row" }} alignItems={{ md: "center" }} gap={2}>
                <ArchiveRounded color="action" />
                <Typography fontFamily="monospace" flex={1}>{String(row.snapshot_code ?? row.id)}</Typography>
                <StatusChip value={String(row.storage_state ?? row.status)} />
                <Button startIcon={<VerifiedRounded />}>Proveri</Button>
                <Button startIcon={<ArchiveRounded />}>Izvezi</Button>
                <Button startIcon={<RestoreRounded />}>Restore</Button>
              </Stack>
            </Paper>
          ))}
        </Stack>
      ) : (
        <EmptyState title="Nema kandidata za arhivu" description="Promenite period ili izaberite drugog dobavljača." />
      )}
    </>
  );
}
