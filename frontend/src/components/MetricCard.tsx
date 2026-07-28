import type { ReactNode } from "react";
import { Box, Paper, Skeleton, Stack, Tooltip, Typography } from "@mui/material";

export function MetricCard({
  title,
  value,
  icon,
  caption,
  loading,
  tone = "primary"
}: {
  title: string;
  value?: number | string | null;
  icon: ReactNode;
  caption: string;
  loading?: boolean;
  tone?: "primary" | "warning" | "error" | "success";
}) {
  return (
    <Tooltip title={caption}>
      <Paper sx={{ p: 2.25, minHeight: 132 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="start">
          <Box>
            <Typography color="text.secondary" variant="body2" fontWeight={650}>
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={72} height={48} />
            ) : (
              <Typography variant="h1" sx={{ mt: 1 }}>
                {value ?? "—"}
              </Typography>
            )}
          </Box>
          <Box
            sx={{
              color: `${tone}.main`,
              bgcolor: `${tone}.main`,
              backgroundImage:
                "linear-gradient(rgba(255,255,255,.88),rgba(255,255,255,.88))",
              borderRadius: 2,
              p: 1,
              display: "flex"
            }}
          >
            {icon}
          </Box>
        </Stack>
      </Paper>
    </Tooltip>
  );
}
