import { LockOutlined } from "@mui/icons-material";
import { Alert, Box, Button, Paper, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { firstAccessiblePath } from "../accessControl";
import { useAuth } from "../state/AuthContext";

export function PermissionRoute({
  permission,
  children
}: {
  permission: string;
  children: ReactNode;
}) {
  const auth = useAuth();
  if (auth.can(permission)) return children;

  const fallback = firstAccessiblePath(auth.permissions);
  return (
    <Box display="grid" sx={{ minHeight: "55vh", placeItems: "center" }}>
      <Paper variant="outlined" sx={{ maxWidth: 560, p: 4, textAlign: "center" }}>
        <Stack alignItems="center" gap={2}>
          <LockOutlined color="warning" sx={{ fontSize: 44 }} />
          <Typography variant="h1">Nemate pristup ovoj stranici</Typography>
          <Alert severity="info" sx={{ textAlign: "left", width: "100%" }}>
            Vaša prijava je važeća, ali nalog nema pravo <strong>{permission}</strong>.
            Pokušaj je bezbedno zaustavljen i podaci nisu promenjeni.
          </Alert>
          {fallback && (
            <Button component={Link} to={fallback} variant="contained">
              Otvori dozvoljenu početnu stranicu
            </Button>
          )}
        </Stack>
      </Paper>
    </Box>
  );
}
