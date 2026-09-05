import { CancelRounded, CheckCircleRounded } from "@mui/icons-material";
import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Card, CardActionArea, CardContent, Grid, Paper, Stack, Typography } from "@mui/material";

import type { SourceProbeResult } from "../../types";
import { methods, type ConnectionForm } from "./sourceForm";

export function SourceMethodStep({ form, onUpdate }: { form: ConnectionForm; onUpdate: (key: keyof ConnectionForm, value: string | boolean) => void }) {
  return (
                    <Grid container spacing={2}>
                      {methods.map(([value, title, description]) => (
                        <Grid item xs={12} sm={6} key={value}>
                          <Card
                            variant="outlined"
                            sx={(theme) => ({
                              height: "100%",
                              borderWidth: form.method === value ? 2 : 1,
                              borderColor:
                                form.method === value ? "primary.main" : "divider",
                              bgcolor:
                                form.method === value
                                  ? theme.palette.action.selected
                                  : "background.paper",
                              transition:
                                "border-color 150ms ease, background-color 150ms ease",
                            })}
                          >
                            <CardActionArea onClick={() => onUpdate("method", value)}>
                              <CardContent>
                                <Stack
                                  direction="row"
                                  justifyContent="space-between"
                                  alignItems="center"
                                >
                                  <Typography variant="h6">{title}</Typography>
                                  {form.method === value && (
                                    <CheckCircleRounded
                                      color="primary"
                                      aria-label="Izabrano"
                                    />
                                  )}
                                </Stack>
                                <Typography
                                  color="text.secondary"
                                  variant="body2"
                                  mt={1}
                                >
                                  {description}
                                </Typography>
                              </CardContent>
                            </CardActionArea>
                          </Card>
                        </Grid>
                      ))}
                    </Grid>
  );
}

export function SourceProbeStep({ probe }: { probe: SourceProbeResult }) {
  return (
                    <Stack gap={2}>
                      <Alert severity={probe.successful ? "success" : "error"}>
                        {probe.message}
                      </Alert>
                      <Grid container spacing={1}>
                        {probe.steps.map((item) => (
                          <Grid item xs={12} sm={6} key={item.label}>
                            <Stack direction="row" gap={1} alignItems="center">
                              {item.successful ? (
                                <CheckCircleRounded color="success" />
                              ) : (
                                <CancelRounded color="error" />
                              )}
                              <Typography>{item.label}</Typography>
                            </Stack>
                          </Grid>
                        ))}
                      </Grid>
                      <Typography>
                        Format: {probe.detected_format ?? "nije prepoznat"}
                      </Typography>
                      <Typography>
                        Veličina: {probe.size_bytes.toLocaleString("sr-RS")} bajtova
                      </Typography>
                      <Typography>
                        Pronađeni zapisi: {probe.approximate_record_count ?? "—"}
                      </Typography>
                      {probe.preview.length > 0 && (
                        <Box sx={{ overflowX: "auto" }}>
                          <Typography variant="h6" mb={1}>
                            Pregled prvih zapisa
                          </Typography>
                          <Stack gap={1}>
                            {probe.preview.map((row, index) => (
                              <Paper key={index} variant="outlined" sx={{ p: 1.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Zapis {index + 1}
                                </Typography>
                                <Grid container spacing={1} mt={0.25}>
                                  {Object.entries(row).map(([key, value]) => (
                                    <Grid item xs={12} sm={6} md={4} key={key}>
                                      <Typography
                                        variant="caption"
                                        color="text.secondary"
                                      >
                                        {key}
                                      </Typography>
                                      <Typography sx={{ overflowWrap: "anywhere" }}>
                                        {value == null ? "—" : String(value)}
                                      </Typography>
                                    </Grid>
                                  ))}
                                </Grid>
                              </Paper>
                            ))}
                          </Stack>
                        </Box>
                      )}
                      <Accordion>
                        <AccordionSummary>Tehnički detalji</AccordionSummary>
                        <AccordionDetails>
                          <Typography>
                            HTTP status: {probe.http_status ?? "—"}
                          </Typography>
                          <Typography>
                            Content type: {probe.content_type ?? "—"}
                          </Typography>
                          <Typography>Trajanje: {probe.duration_ms} ms</Typography>
                          <Typography>Checksum: {probe.checksum ?? "—"}</Typography>
                        </AccordionDetails>
                      </Accordion>
                    </Stack>
  );
}
