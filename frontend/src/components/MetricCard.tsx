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
      <Paper sx={{ p: 1.15, minHeight: 78, height: "100%", overflow: "hidden" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Box sx={{ minWidth: 0 }}>
            <Typography
              color="text.secondary"
              variant="caption"
              fontWeight={700}
              sx={{
                display: "-webkit-box",
                WebkitBoxOrient: "vertical",
                WebkitLineClamp: 2,
                overflow: "hidden",
                lineHeight: 1.2,
                fontSize: "0.7rem",
                minHeight: "1.68rem"
              }}
            >
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={36} height={30} />
            ) : (
              <Typography
                component="strong"
                sx={{
                  display: "block",
                  mt: 0.25,
                  fontSize: "1.3rem",
                  lineHeight: 1,
                  fontWeight: 750
                }}
              >
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
              borderRadius: 1.25,
              p: 0.55,
              display: "flex",
              flexShrink: 0,
              ml: 0.75,
              "& .MuiSvgIcon-root": { fontSize: 17 },
              "@media (max-width:360px)": {
                display: "none"
              }
            }}
          >
            {icon}
          </Box>
        </Stack>
      </Paper>
    </Tooltip>
  );
}
