import type { Dispatch, SetStateAction } from "react";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField } from "@mui/material";

import type { ConnectionForm } from "./sourceForm";

type Props = {
  open: boolean;
  form: ConnectionForm;
  certificateFile: File | null;
  saving: boolean;
  onClose: () => void;
  onSave: () => void;
  onAuthenticationType: (value: string) => void;
  onUpdate: <K extends keyof ConnectionForm>(key: K, value: ConnectionForm[K]) => void;
  setCertificateFile: Dispatch<SetStateAction<File | null>>;
};

export function SourceCredentialsDialog({ open, form, certificateFile, saving, onClose, onSave, onAuthenticationType, onUpdate, setCertificateFile }: Props) {
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Promeni pristupne podatke</DialogTitle>
      <DialogContent>
        <Stack gap={2} mt={1}>
          <TextField select label="Način prijave" value={form.authentication_type} onChange={(event) => onAuthenticationType(event.target.value)}>
            <MenuItem value="BASIC">Korisničko ime i lozinka</MenuItem>
            <MenuItem value="BEARER">Bearer token</MenuItem>
            <MenuItem value="API_KEY">API ključ</MenuItem>
            <MenuItem value="CLIENT_CERTIFICATE">Klijentski sertifikat (mTLS)</MenuItem>
            <MenuItem value="SOAP_BODY">SOAP servis (CT / PIN-ALSO)</MenuItem>
          </TextField>
          {form.integration_profile !== "ASBIS_IT4PROFIT" && !["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(form.authentication_type) && (
            <TextField select label="Gde dobavljač očekuje pristupne podatke" value={form.placement} onChange={(event) => onUpdate("placement", event.target.value)}>
              <MenuItem value="HEADER">Bezbednosno zaglavlje</MenuItem><MenuItem value="QUERY">Parametri adrese</MenuItem>
            </TextField>
          )}
          {form.integration_profile === "ASBIS_IT4PROFIT" && <Alert severity="info">ASBIS API koristi fiksne URL parametre USERNAME i PASSWORD.</Alert>}
          {(form.authentication_type === "BASIC" || (form.authentication_type === "SOAP_BODY" && form.integration_profile === "CT_SOAP")) && <>
            <TextField label="Korisničko ime" value={form.username} onChange={(event) => onUpdate("username", event.target.value)} />
            <TextField type="password" label="Lozinka" value={form.password} onChange={(event) => onUpdate("password", event.target.value)} />
          </>}
          {form.authentication_type === "BEARER" && <TextField type="password" label="Token" value={form.token} onChange={(event) => onUpdate("token", event.target.value)} />}
          {form.authentication_type === "API_KEY" && <TextField type="password" label="API ključ" value={form.api_key} onChange={(event) => onUpdate("api_key", event.target.value)} />}
          {form.integration_profile === "ASBIS_IT4PROFIT" && <>
            <Alert severity="info">API i email lozinke čuvaju se zajedno u postojećem zaštićenom fajlu, van baze.</Alert>
            <TextField label="IMAP korisničko ime" value={form.imap_username} onChange={(event) => onUpdate("imap_username", event.target.value)} />
            <TextField type="password" label="IMAP lozinka" value={form.imap_password} onChange={(event) => onUpdate("imap_password", event.target.value)} />
          </>}
          {form.authentication_type === "SOAP_BODY" && form.integration_profile === "PIN_SOAP" && <>
            <TextField type="password" label="Klijentski kod (GUID)" value={form.api_key} onChange={(event) => onUpdate("api_key", event.target.value)} />
            <TextField label="Shop ID" value={form.pin_shop_id} onChange={(event) => onUpdate("pin_shop_id", event.target.value)} helperText="Podrazumevana vrednost je 4." />
          </>}
          {!['CLIENT_CERTIFICATE', 'SOAP_BODY'].includes(form.authentication_type) && form.placement === "QUERY" && <Stack direction={{ xs: "column", sm: "row" }} gap={2}>
            <TextField fullWidth label="Naziv parametra korisničkog imena" value={form.username_parameter} onChange={(event) => onUpdate("username_parameter", event.target.value)} />
            <TextField fullWidth label="Naziv parametra lozinke" value={form.password_parameter} onChange={(event) => onUpdate("password_parameter", event.target.value)} />
          </Stack>}
          {form.authentication_type === "CLIENT_CERTIFICATE" && <>
            <Alert severity="info">Novi sertifikat će zameniti postojeći tek nakon uspešne provere fajla i lozinke.</Alert>
            <Button component="label" variant="outlined">{certificateFile ? certificateFile.name : "Izaberi novi .p12 / .pfx sertifikat"}<input hidden type="file" accept=".p12,.pfx,application/x-pkcs12" onChange={(event) => setCertificateFile(event.target.files?.[0] ?? null)} /></Button>
            <TextField type="password" label="Lozinka sertifikata" value={form.certificate_password} onChange={(event) => onUpdate("certificate_password", event.target.value)} />
          </>}
        </Stack>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Otkaži</Button><Button variant="contained" onClick={onSave} disabled={saving}>Sačuvaj pristupne podatke</Button></DialogActions>
    </Dialog>
  );
}
