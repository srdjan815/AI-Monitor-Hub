import { Paper, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return <Paper variant="outlined" sx={{ p: 2 }}><Typography variant="h6" mb={1.5}>{title}</Typography><Stack gap={1}>{children}</Stack></Paper>;
}

export function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={0.5}><Typography color="text.secondary">{label}</Typography><Typography fontWeight={600} textAlign={{ sm: "right" }}>{value}</Typography></Stack>;
}
