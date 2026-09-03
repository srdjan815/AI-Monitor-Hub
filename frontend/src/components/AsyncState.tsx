import type { ReactNode } from "react";
import { ErrorOutlineRounded, InboxRounded } from "@mui/icons-material";
import { Alert, Box, Button, Skeleton, Stack, Typography } from "@mui/material";
import type { ApiError } from "../types";

export function LoadingBlock({ rows = 5 }: { rows?: number }) {
  return (
    <Stack gap={1.2} aria-label="Učitavanje">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} variant="rounded" height={48} />
      ))}
    </Stack>
  );
}

export function ErrorBlock({
  error,
  retry
}: {
  error: unknown;
  retry?: () => void;
}) {
  const value = error as ApiError;
  return (
    <Alert
      severity="error"
      icon={<ErrorOutlineRounded />}
      action={
        retry && (
          <Button color="inherit" onClick={retry}>
            Pokušaj ponovo
          </Button>
        )
      }
    >
      <strong>{value.code || "GREŠKA"}</strong>:{" "}
      {value.message || "Podaci trenutno nisu dostupni."}
      {value.requestId && (
        <Typography display="block" variant="caption">
          Request ID: {value.requestId}
        </Typography>
      )}
    </Alert>
  );
}

export function EmptyState({
  title = "Nema rezultata",
  description = "Promenite filtere ili kreirajte prvi zapis.",
  action
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Box textAlign="center" py={7}>
      <InboxRounded color="disabled" sx={{ fontSize: 48 }} />
      <Typography variant="h3" mt={1}>{title}</Typography>
      <Typography color="text.secondary" mt={0.5}>{description}</Typography>
      {action && <Box mt={2}>{action}</Box>}
    </Box>
  );
}
