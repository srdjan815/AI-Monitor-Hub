import type { Dispatch, SetStateAction } from "react";
import { Alert, Button, FormControlLabel, MenuItem, Stack, Switch, TextField } from "@mui/material";

import type { ConnectionForm } from "./sourceForm";
import { SourceAdvancedSettings, SourceNonHttpFields } from "./SourceProtocolFields";

type Props = {
  form: ConnectionForm;
  networkSupported: boolean;
  probeFile: File | null;
  certificateFile: File | null;
  onUpdate: (key: keyof ConnectionForm, value: string | boolean) => void;
  onAuthenticationType: (value: string) => void;
  onSoapProfile: (value: string) => void;
  onIntegrationProfile: (value: string) => void;
  setProbeFile: Dispatch<SetStateAction<File | null>>;
  setCertificateFile: Dispatch<SetStateAction<File | null>>;
};

export function SourceConfigurationStep({ form, networkSupported, probeFile, certificateFile, onUpdate: update, onAuthenticationType: selectAuthenticationType, onSoapProfile: selectSoapProfile, onIntegrationProfile: selectIntegrationProfile, setProbeFile, setCertificateFile }: Props) {
  return (
                    <Stack gap={2} mt={1}>
                      <TextField
                        label="Naziv konekcije"
                        required
                        value={form.name}
                        helperText="Na primer: Glavni XML cenovnik."
                        onChange={(event) => update("name", event.target.value)}
                      />
                      <TextField
                        label="Šifra dobavljača na portalu"
                        value={form.portal_supplier_code}
                        onChange={(event) =>
                          update("portal_supplier_code", event.target.value)
                        }
                        helperText="Partnerska šifra koju ovaj portal koristi; nije lozinka."
                      />
                      {["HTTP", "API", "PORTAL", "MANUAL_UPLOAD"].includes(
                        form.method,
                      ) && (
                        <TextField
                          select
                          label="Format cenovnika"
                          value={form.format}
                          helperText="Izaberite format ili dozvolite automatsko prepoznavanje."
                          onChange={(event) => update("format", event.target.value)}
                        >
                          {["AUTO", "XML", "EXCEL", "CSV", "JSON"].map((item) => (
                            <MenuItem key={item} value={item}>
                              {item === "AUTO" ? "Automatsko prepoznavanje" : item}
                            </MenuItem>
                          ))}
                        </TextField>
                      )}
                      {["HTTP", "API", "PORTAL"].includes(form.method) && (
                        <>
                          <TextField
                            label={
                              form.method === "API"
                                ? "Osnovni URL"
                                : "URL za preuzimanje"
                            }
                            required
                            value={form.url}
                            helperText="Adresa sa koje sistem preuzima cenovnik."
                            onChange={(event) => update("url", event.target.value)}
                          />
                          {form.method === "API" && (
                            <>
                              <TextField
                                select
                                label="Profil integracije"
                                value={form.integration_profile}
                                onChange={(event) =>
                                  selectIntegrationProfile(event.target.value)
                                }
                              >
                                <MenuItem value="GENERIC">Opšti API</MenuItem>
                                <MenuItem value="ASBIS_IT4PROFIT">
                                  ASBIS (2 XML + akcije iz emaila)
                                </MenuItem>
                                <MenuItem value="KIMTEC_MSAN">
                                  KimTec / M SAN B2B
                                </MenuItem>
                              </TextField>
                              {form.integration_profile === "ASBIS_IT4PROFIT" ? (
                                <>
                                  <Alert severity="info">
                                    Katalog i stanje/cene spajaju se sa poslednjim ASBIS
                                    akcijskim ZIP prilogom po šifri artikla.
                                  </Alert>
                                  <TextField
                                    label="Prvi XML — katalog proizvoda"
                                    value={form.catalog_endpoint}
                                    helperText={`${form.url.replace(/\/$/, "")}/${form.catalog_endpoint.replace(/^\//, "")} (USERNAME i PASSWORD sistem dodaje bez prikazivanja)`}
                                    onChange={(event) =>
                                      update("catalog_endpoint", event.target.value)
                                    }
                                  />
                                  <TextField
                                    label="Drugi XML — cene i stanje"
                                    value={form.price_endpoint}
                                    helperText={`${form.url.replace(/\/$/, "")}/${form.price_endpoint.replace(/^\//, "")} (USERNAME i PASSWORD sistem dodaje bez prikazivanja)`}
                                    onChange={(event) =>
                                      update("price_endpoint", event.target.value)
                                    }
                                  />
                                  <TextField
                                    label="IMAP server"
                                    value={form.imap_host}
                                    onChange={(event) =>
                                      update("imap_host", event.target.value)
                                    }
                                  />
                                  <TextField
                                    label="IMAP port"
                                    value={form.imap_port}
                                    onChange={(event) =>
                                      update("imap_port", event.target.value)
                                    }
                                  />
                                  <TextField
                                    label="Dozvoljeni pošiljalac"
                                    value={form.sender}
                                    helperText="Opciono, ali preporučeno: email adresa ili stabilan deo From zaglavlja ASBIS poruke."
                                    onChange={(event) =>
                                      update("sender", event.target.value)
                                    }
                                  />
                                  <TextField
                                    label="IMAP korisničko ime"
                                    value={form.imap_username}
                                    onChange={(event) =>
                                      update("imap_username", event.target.value)
                                    }
                                  />
                                  <TextField
                                    type="password"
                                    label="IMAP lozinka"
                                    value={form.imap_password}
                                    onChange={(event) =>
                                      update("imap_password", event.target.value)
                                    }
                                  />
                                </>
                              ) : (
                                <TextField
                                  label="Endpoint"
                                  value={form.endpoint}
                                  helperText="Putanja API operacije, na primer /v1/products."
                                  onChange={(event) =>
                                    update("endpoint", event.target.value)
                                  }
                                />
                              )}
                            </>
                          )}
                          {form.method === "PORTAL" && (
                            <>
                              <Alert severity="info">
                                Sistem otvara login stranicu, čuva session cookie samo
                                tokom ovog izvršavanja i zatim preuzima cenovnik.
                              </Alert>
                              <TextField
                                label="URL stranice za prijavu"
                                required
                                value={form.login_url}
                                helperText="Adresa na kojoj se prikazuje forma za prijavu na B2B portal."
                                onChange={(event) =>
                                  update("login_url", event.target.value)
                                }
                              />
                              <TextField
                                label="Korisničko ime"
                                required
                                value={form.username}
                                onChange={(event) =>
                                  update("username", event.target.value)
                                }
                              />
                              <TextField
                                type="password"
                                label="Lozinka"
                                required
                                value={form.password}
                                onChange={(event) =>
                                  update("password", event.target.value)
                                }
                              />
                            </>
                          )}
                          {form.method !== "PORTAL" && (
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={form.login_required || form.method === "API"}
                                  onChange={(event) =>
                                    update("login_required", event.target.checked)
                                  }
                                  disabled={form.method === "API"}
                                />
                              }
                              label="Potrebna je prijava"
                            />
                          )}
                          {form.method !== "PORTAL" &&
                            (form.login_required || form.method === "API") && (
                              <>
                                <TextField
                                  select
                                  label="Način prijave"
                                  value={form.authentication_type}
                                  onChange={(event) =>
                                    selectAuthenticationType(event.target.value)
                                  }
                                >
                                  <MenuItem value="NONE">Bez prijave</MenuItem>
                                  <MenuItem value="BASIC">
                                    Korisničko ime i lozinka
                                  </MenuItem>
                                  <MenuItem value="BEARER">Bearer token</MenuItem>
                                  <MenuItem value="API_KEY">API ključ</MenuItem>
                                  <MenuItem value="CLIENT_CERTIFICATE">
                                    Klijentski sertifikat (mTLS)
                                  </MenuItem>
                                  <MenuItem value="SOAP_BODY">
                                    SOAP servis (CT / PIN-ALSO)
                                  </MenuItem>
                                </TextField>
                                {form.integration_profile !== "ASBIS_IT4PROFIT" &&
                                  !["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(
                                    form.authentication_type,
                                  ) && (
                                    <TextField
                                      select
                                      label="Gde dobavljač očekuje podatke za prijavu"
                                      value={form.placement}
                                      onChange={(event) =>
                                        update("placement", event.target.value)
                                      }
                                    >
                                      <MenuItem value="HEADER">
                                        Bezbednosno zaglavlje
                                      </MenuItem>
                                      <MenuItem value="QUERY">
                                        Parametri adrese (npr. DS Computers)
                                      </MenuItem>
                                    </TextField>
                                  )}
                                {form.integration_profile === "ASBIS_IT4PROFIT" && (
                                  <Alert severity="info">
                                    ASBIS API prijava je fiksno podešena kroz URL
                                    parametre USERNAME i PASSWORD.
                                  </Alert>
                                )}
                                {(form.authentication_type === "BASIC" ||
                                  form.authentication_type === "API_KEY" ||
                                  (form.authentication_type === "SOAP_BODY" &&
                                    form.integration_profile === "CT_SOAP")) && (
                                  <TextField
                                    label="Korisničko ime"
                                    value={form.username}
                                    onChange={(event) =>
                                      update("username", event.target.value)
                                    }
                                  />
                                )}
                                {(form.authentication_type === "BASIC" ||
                                  (form.authentication_type === "SOAP_BODY" &&
                                    form.integration_profile === "CT_SOAP")) && (
                                  <TextField
                                    type="password"
                                    label="Lozinka"
                                    value={form.password}
                                    onChange={(event) =>
                                      update("password", event.target.value)
                                    }
                                  />
                                )}
                                {form.authentication_type === "SOAP_BODY" && (
                                  <>
                                    <TextField
                                      select
                                      label="SOAP profil integracije"
                                      value={form.integration_profile}
                                      onChange={(event) =>
                                        selectSoapProfile(event.target.value)
                                      }
                                    >
                                      <MenuItem value="CT_SOAP">CT Computers</MenuItem>
                                      <MenuItem value="PIN_SOAP">
                                        PIN / ALSO Srbija
                                      </MenuItem>
                                    </TextField>
                                    {form.integration_profile === "PIN_SOAP" ? (
                                      <>
                                        <Alert severity="info">
                                          Preuzimaju se samo artikli koje PIN/ALSO
                                          označi kao dostupne na stanju. GUID se trajno
                                          čuva van baze.
                                        </Alert>
                                        <TextField
                                          label="Klijentski kod (GUID)"
                                          type="password"
                                          value={form.api_key}
                                          onChange={(event) =>
                                            update("api_key", event.target.value)
                                          }
                                        />
                                        <TextField
                                          label="Shop ID"
                                          value={form.pin_shop_id}
                                          onChange={(event) =>
                                            update("pin_shop_id", event.target.value)
                                          }
                                          helperText="Podrazumevana vrednost prema dokumentaciji je 4."
                                        />
                                      </>
                                    ) : (
                                      <Alert severity="info">
                                        Pristupni podaci se trajno čuvaju van baze.
                                        Sistem ih šalje samo unutar CT SOAP zahteva;
                                        javna IP adresa aplikacije mora biti odobrena
                                        kod dobavljača.
                                      </Alert>
                                    )}
                                  </>
                                )}
                                {form.authentication_type === "BEARER" && (
                                  <TextField
                                    type="password"
                                    label="Token"
                                    value={form.token}
                                    onChange={(event) =>
                                      update("token", event.target.value)
                                    }
                                  />
                                )}
                                {form.authentication_type === "API_KEY" && (
                                  <TextField
                                    type="password"
                                    label="API ključ ili lozinka"
                                    value={form.api_key}
                                    onChange={(event) =>
                                      update("api_key", event.target.value)
                                    }
                                  />
                                )}
                                {form.authentication_type === "CLIENT_CERTIFICATE" && (
                                  <>
                                    <TextField
                                      select
                                      label="Profil integracije"
                                      value={form.integration_profile}
                                      onChange={(event) =>
                                        selectIntegrationProfile(event.target.value)
                                      }
                                    >
                                      <MenuItem value="GENERIC">
                                        Opšti mTLS API
                                      </MenuItem>
                                      <MenuItem value="KIMTEC_MSAN">
                                        KimTec / M SAN B2B
                                      </MenuItem>
                                    </TextField>
                                    {form.integration_profile === "KIMTEC_MSAN" && (
                                      <>
                                        <Alert severity="info">
                                          Sistem preuzima katalog, cenovnik i EAN
                                          barkodove istim sertifikatom i spaja ih po
                                          ProductCode.
                                        </Alert>
                                        <TextField
                                          label="Endpoint kataloga"
                                          value={form.catalog_endpoint}
                                          onChange={(event) =>
                                            update(
                                              "catalog_endpoint",
                                              event.target.value,
                                            )
                                          }
                                        />
                                        <TextField
                                          label="Endpoint cenovnika"
                                          value={form.price_endpoint}
                                          onChange={(event) =>
                                            update("price_endpoint", event.target.value)
                                          }
                                        />
                                        <TextField
                                          label="SOAP servis za EAN barkodove"
                                          value={form.barcode_service_url}
                                          onChange={(event) =>
                                            update(
                                              "barcode_service_url",
                                              event.target.value,
                                            )
                                          }
                                        />
                                      </>
                                    )}
                                    <Button component="label" variant="outlined">
                                      {certificateFile
                                        ? certificateFile.name
                                        : "Izaberi .p12 / .pfx sertifikat"}
                                      <input
                                        hidden
                                        type="file"
                                        accept=".p12,.pfx,application/x-pkcs12"
                                        onChange={(event) =>
                                          setCertificateFile(
                                            event.target.files?.[0] ?? null,
                                          )
                                        }
                                      />
                                    </Button>
                                    <TextField
                                      type="password"
                                      label="Lozinka sertifikata"
                                      value={form.certificate_password}
                                      helperText="Unosi se samo pri prvom čuvanju ili zameni sertifikata."
                                      onChange={(event) =>
                                        update(
                                          "certificate_password",
                                          event.target.value,
                                        )
                                      }
                                    />
                                  </>
                                )}
                                {!["CLIENT_CERTIFICATE", "SOAP_BODY"].includes(
                                  form.authentication_type,
                                ) &&
                                  form.placement === "QUERY" && (
                                    <Stack
                                      direction={{ xs: "column", sm: "row" }}
                                      gap={2}
                                    >
                                      <TextField
                                        fullWidth
                                        label="Naziv parametra korisničkog imena"
                                        value={form.username_parameter}
                                        onChange={(event) =>
                                          update(
                                            "username_parameter",
                                            event.target.value,
                                          )
                                        }
                                      />
                                      <TextField
                                        fullWidth
                                        label="Naziv parametra lozinke"
                                        value={form.password_parameter}
                                        onChange={(event) =>
                                          update(
                                            "password_parameter",
                                            event.target.value,
                                          )
                                        }
                                      />
                                    </Stack>
                                  )}
                              </>
                            )}
                        </>
                      )}
                      <SourceNonHttpFields form={form} probeFile={probeFile} onUpdate={update} setProbeFile={setProbeFile} />
                      <SourceAdvancedSettings form={form} onUpdate={update} />
                      <TextField
                        multiline
                        minRows={2}
                        label="Opis"
                        value={form.description}
                        onChange={(event) => update("description", event.target.value)}
                      />
                      {!networkSupported && form.method !== "MANUAL_UPLOAD" && (
                        <Alert severity="info">
                          Automatsko preuzimanje za ovaj tip izvora biće dostupno u
                          narednoj fazi razvoja. Podešavanja možete sačuvati kao nacrt.
                        </Alert>
                      )}
                    </Stack>
  );
}
