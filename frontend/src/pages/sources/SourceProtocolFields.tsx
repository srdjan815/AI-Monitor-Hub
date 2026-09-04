import type { Dispatch, SetStateAction } from "react";
import { Accordion, AccordionDetails, AccordionSummary, Button, Checkbox, FormControlLabel, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import type { ConnectionForm } from "./sourceForm";

type CommonProps = { form: ConnectionForm; onUpdate: (key: keyof ConnectionForm, value: string | boolean) => void };

export function SourceNonHttpFields({ form, probeFile, onUpdate: update, setProbeFile }: CommonProps & { probeFile: File | null; setProbeFile: Dispatch<SetStateAction<File | null>> }) {
  return <>
                          {["FTP", "SFTP"].includes(form.method) && (
                            <>
                              <TextField
                                label="Server"
                                required
                                value={form.host}
                                onChange={(event) => update("host", event.target.value)}
                              />
                              <TextField
                                label="Port"
                                value={form.port}
                                helperText="Ostavite prazno za standardni port."
                                onChange={(event) => update("port", event.target.value)}
                              />
                              <TextField
                                label="Korisničko ime"
                                value={form.username}
                                onChange={(event) => update("username", event.target.value)}
                              />
                              <TextField
                                type="password"
                                label="Lozinka ili ključ"
                                value={form.password}
                                onChange={(event) => update("password", event.target.value)}
                              />
                              <TextField
                                label="Udaljena putanja"
                                value={form.remote_path}
                                onChange={(event) =>
                                  update("remote_path", event.target.value)
                                }
                              />
                              <TextField
                                label="Šablon naziva fajla"
                                value={form.filename_pattern}
                                onChange={(event) =>
                                  update("filename_pattern", event.target.value)
                                }
                              />
                            </>
                          )}
                          {form.method === "EMAIL" && (
                            <>
                              <TextField
                                label="Mailbox"
                                required
                                value={form.mailbox}
                                onChange={(event) => update("mailbox", event.target.value)}
                              />
                              <TextField
                                label="Folder"
                                value={form.folder}
                                onChange={(event) => update("folder", event.target.value)}
                              />
                              <TextField
                                label="Pošiljalac"
                                value={form.sender}
                                onChange={(event) => update("sender", event.target.value)}
                              />
                              <TextField
                                label="Deo naslova poruke"
                                value={form.subject}
                                onChange={(event) => update("subject", event.target.value)}
                              />
                              <TextField
                                label="Šablon naziva priloga"
                                required
                                value={form.filename_pattern}
                                onChange={(event) =>
                                  update("filename_pattern", event.target.value)
                                }
                              />
                              <TextField
                                type="password"
                                label="Pristupni podaci"
                                value={form.password}
                                onChange={(event) => update("password", event.target.value)}
                              />
                            </>
                          )}
                          {form.method === "GOOGLE_DRIVE" && (
                            <>
                              <TextField
                                label="File ID"
                                value={form.file_id}
                                onChange={(event) => update("file_id", event.target.value)}
                              />
                              <TextField
                                label="Folder ID"
                                value={form.folder_id}
                                onChange={(event) =>
                                  update("folder_id", event.target.value)
                                }
                              />
                              <TextField
                                label="Šablon naziva fajla"
                                value={form.filename_pattern}
                                onChange={(event) =>
                                  update("filename_pattern", event.target.value)
                                }
                              />
                              <TextField
                                label="Shared Drive ID"
                                value={form.shared_drive_id}
                                onChange={(event) =>
                                  update("shared_drive_id", event.target.value)
                                }
                              />
                            </>
                          )}
                          {form.method === "MANUAL_UPLOAD" && (
                            <>
                              <TextField
                                label="Maksimalna veličina fajla (MB)"
                                value={form.maximum_mb}
                                onChange={(event) =>
                                  update("maximum_mb", event.target.value)
                                }
                              />
                              <TextField
                                label="Šablon naziva fajla"
                                value={form.filename_pattern}
                                onChange={(event) =>
                                  update("filename_pattern", event.target.value)
                                }
                              />
                              <Button component="label" variant="outlined">
                                {probeFile ? probeFile.name : "Izaberi probni fajl"}
                                <input
                                  hidden
                                  type="file"
                                  accept=".xml,.csv,.xlsx"
                                  onChange={(event) =>
                                    setProbeFile(event.target.files?.[0] ?? null)
                                  }
                                />
                              </Button>
                              <Typography variant="caption" color="text.secondary">
                                Probni fajl se analizira u memoriji i ne pokreće
                                Acquisition.
                              </Typography>
                            </>
                          )}
  </>;
}

export function SourceAdvancedSettings({ form, onUpdate: update }: CommonProps) {
  return (
                          <Accordion>
                            <AccordionSummary>Napredna podešavanja</AccordionSummary>
                            <AccordionDetails>
                              <Stack gap={2}>
                                {["HTTP", "API", "PORTAL"].includes(form.method) && (
                                  <>
                                    <TextField
                                      select
                                      label="Metod"
                                      value={form.http_method}
                                      onChange={(event) =>
                                        update("http_method", event.target.value)
                                      }
                                    >
                                      <MenuItem value="GET">GET</MenuItem>
                                      <MenuItem value="POST">POST</MenuItem>
                                    </TextField>
                                    <TextField
                                      multiline
                                      minRows={2}
                                      label="Javni parametri"
                                      value={form.public_query}
                                      helperText="Jedan parametar po redu: naziv=vrednost. Ne unosite lozinke."
                                      onChange={(event) =>
                                        update("public_query", event.target.value)
                                      }
                                    />
                                    <TextField
                                      multiline
                                      minRows={2}
                                      label="Javna zaglavlja"
                                      value={form.public_headers}
                                      helperText="Jedno zaglavlje po redu: naziv=vrednost."
                                      onChange={(event) =>
                                        update("public_headers", event.target.value)
                                      }
                                    />
                                    {form.method === "PORTAL" && (
                                      <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography fontWeight={700} mb={0.5}>
                                          Tehnički nazivi login polja
                                        </Typography>
                                        <Typography
                                          variant="body2"
                                          color="text.secondary"
                                          mb={2}
                                        >
                                          Ovo nisu dodatni pristupni podaci. Menjaju se samo
                                          kada portal koristi drugačije HTML nazive polja.
                                          Za EPI Computers unesite „user“ i „pass“.
                                        </Typography>
                                        <Stack
                                          direction={{ xs: "column", sm: "row" }}
                                          gap={2}
                                        >
                                          <TextField
                                            fullWidth
                                            label="HTML polje korisničkog imena"
                                            required
                                            value={form.username_field}
                                            helperText="Najčešće: username ili user."
                                            onChange={(event) =>
                                              update("username_field", event.target.value)
                                            }
                                          />
                                          <TextField
                                            fullWidth
                                            label="HTML polje lozinke"
                                            required
                                            value={form.password_field}
                                            helperText="Najčešće: password ili pass."
                                            onChange={(event) =>
                                              update("password_field", event.target.value)
                                            }
                                          />
                                        </Stack>
                                        <Stack gap={2} mt={2}>
                                          <TextField
                                            label="URL za slanje prijave (opciono)"
                                            value={form.login_submit_url}
                                            helperText="Ostavite prazno da sistem automatski koristi action iz login forme."
                                            onChange={(event) =>
                                              update("login_submit_url", event.target.value)
                                            }
                                          />
                                          <TextField
                                            multiline
                                            minRows={2}
                                            label="Dodatna javna polja login forme"
                                            value={form.login_form_fields}
                                            helperText="Samo netajna polja, jedno po redu: naziv=vrednost. Hidden/CSRF polja sistem preuzima automatski."
                                            onChange={(event) =>
                                              update(
                                                "login_form_fields",
                                                event.target.value,
                                              )
                                            }
                                          />
                                        </Stack>
                                      </Paper>
                                    )}
                                  </>
                                )}
                                <TextField
                                  label="Maksimalno čekanje (sekunde)"
                                  value={form.timeout}
                                  onChange={(event) =>
                                    update("timeout", event.target.value)
                                  }
                                />
                                <FormControlLabel
                                  control={
                                    <Checkbox
                                      checked={form.verify_tls}
                                      onChange={(event) =>
                                        update("verify_tls", event.target.checked)
                                      }
                                    />
                                  }
                                  label="Proveri bezbednosni sertifikat"
                                />
                              </Stack>
                            </AccordionDetails>
                          </Accordion>
  );
}
