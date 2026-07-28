import type { ReactNode } from "react";
import { CloseRounded } from "@mui/icons-material";
import {
  Box,
  Divider,
  Drawer,
  IconButton,
  Stack,
  Tooltip,
  Typography
} from "@mui/material";

export function DetailDrawer({
  open,
  title,
  subtitle,
  onClose,
  children,
  actions
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 520 }, maxWidth: "100%" } }}
    >
      <Stack direction="row" alignItems="start" p={2.5} gap={2}>
        <Box flex={1}>
          <Typography variant="h2">{title}</Typography>
          {subtitle && (
            <Typography color="text.secondary" variant="body2" mt={0.5}>
              {subtitle}
            </Typography>
          )}
        </Box>
        <Tooltip title="Zatvori detalje">
          <IconButton onClick={onClose} aria-label="Zatvori detalje">
            <CloseRounded />
          </IconButton>
        </Tooltip>
      </Stack>
      {actions && (
        <>
          <Stack direction="row" gap={1} px={2.5} pb={2} flexWrap="wrap">
            {actions}
          </Stack>
          <Divider />
        </>
      )}
      <Box p={2.5} overflow="auto">{children}</Box>
    </Drawer>
  );
}
