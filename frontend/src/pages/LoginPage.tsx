import { useState } from "react";
import { KeyRounded, LockRounded } from "@mui/icons-material";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  CssBaseline,
  Stack,
  TextField,
  ThemeProvider,
  Tooltip,
  Typography
} from "@mui/material";
import { useAuth } from "../state/AuthContext";
import { usePreferences } from "../state/PreferencesContext";
import { createAppTheme } from "../theme";

export function LoginPage() {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const auth = useAuth();
  const preferences = usePreferences();
  const submit = async () => {
    if (!token.trim()) {
      setError("Unesite administratorski Bearer token.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await auth.login(token);
      setToken("");
    } catch {
      setError("Prijava nije uspela. Proverite token.");
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <ThemeProvider theme={createAppTheme(preferences.resolvedTheme)}>
      <CssBaseline />
      <Box
        minHeight="100vh"
        display="grid"
        sx={{
          placeItems: "center",
          p: 2,
          background:
            "radial-gradient(circle at 15% 20%, rgba(22,164,167,.16), transparent 32%), radial-gradient(circle at 85% 80%, rgba(18,48,71,.18), transparent 34%)"
        }}
      >
        <Card sx={{ width: "100%", maxWidth: 460 }}>
          <CardContent sx={{ p: { xs: 3, sm: 5 } }}>
            <Stack alignItems="center" textAlign="center" mb={3}>
              <Avatar sx={{ bgcolor: "primary.main", width: 56, height: 56, mb: 2 }}>
                <LockRounded />
              </Avatar>
              <Typography variant="h1">Supplier Platform</Typography>
              <Typography color="text.secondary" mt={1}>
                Enterprise administracija dobavljačkih podataka
              </Typography>
            </Stack>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <Tooltip title="Token se podešava u lokalnom .env.secrets fajlu; UI ga ne generiše niti prikazuje.">
              <TextField
                fullWidth
                multiline
                minRows={3}
                label="Administratorski Bearer token"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                autoFocus
                helperText="Token se šalje backend-u i ne čuva se u browser storage-u."
                InputProps={{
                  startAdornment: <KeyRounded color="action" sx={{ mr: 1, alignSelf: "start", mt: 1 }} />
                }}
              />
            </Tooltip>
            <Button fullWidth variant="contained" size="large" onClick={submit} disabled={submitting} sx={{ mt: 2 }}>
              Prijavi se
            </Button>
          </CardContent>
        </Card>
      </Box>
    </ThemeProvider>
  );
}
