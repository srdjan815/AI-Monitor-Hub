import { Alert, Paper, Stack, Typography } from "@mui/material";

import { StatusChip } from "../../components/StatusChip";
import type { Operation, Source, SourceProbeResult, SupplierSchedule } from "../../types";
import { DetailRow, DetailSection } from "./SourceDetails";
import { detailValue, displayFormat, displayMethod, formatDate } from "./sourceDisplay";

type Props = {
  opened: Source;
  sourceSchedule?: SupplierSchedule;
  openedProbe: SourceProbeResult | null;
  schema?: Operation;
  mapping?: Operation;
  acquisition?: Operation;
  snapshot?: Operation;
  delta?: Operation;
};

export function SourceDiagnosticDetails({ opened, sourceSchedule, openedProbe, schema, mapping, acquisition, snapshot, delta }: Props) {
  return (
              <Stack gap={2}>
                <Alert
                  severity={
                    opened.has_secret_reference && !opened.credentials_available
                      ? "warning"
                      : opened.last_validation_status === "VALID"
                        ? "success"
                        : "info"
                  }
                >
                  {opened.has_secret_reference && !opened.credentials_available
                    ? "Pristupni podaci više nisu dostupni. Unesite ih ponovo i ponovite probu."
                    : opened.last_validation_message?.replace(
                        /^PROBE_(?:OK|FAILED): /,
                        "",
                      ) || "Konekcija još nije probno preuzela cenovnik."}
                </Alert>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="h6">Administrativni pregled</Typography>
                  <Typography color="text.secondary" mt={0.5}>
                    Centralna dijagnostika toka od konekcije do Delta obrade.
                  </Typography>
                </Paper>
                <DetailSection title="Connection">
                  <DetailRow
                    label="Status"
                    value={
                      <StatusChip
                        value={opened.is_active ? opened.status : "ARCHIVED"}
                      />
                    }
                  />
                  <DetailRow label="Tip konekcije" value={displayMethod(opened)} />
                  <DetailRow label="Format" value={displayFormat(opened)} />
                </DetailSection>
                <DetailSection title="Automatski raspored">
                  <DetailRow
                    label="Status"
                    value={
                      <StatusChip value={sourceSchedule?.status ?? "MANUAL"} />
                    }
                  />
                  <DetailRow
                    label="Sledeće pokretanje"
                    value={formatDate(sourceSchedule?.next_run_at)}
                  />
                  <DetailRow
                    label="Poslednje pokretanje"
                    value={formatDate(sourceSchedule?.last_run_at)}
                  />
                  <DetailRow
                    label="Poslednji rezultat"
                    value={sourceSchedule?.last_result ?? "Još nije izvršeno"}
                  />
                  <DetailRow
                    label="Uzastopne greške"
                    value={sourceSchedule?.consecutive_failures ?? 0}
                  />
                </DetailSection>
                <DetailSection title="Last Probe">
                  <DetailRow
                    label="Datum"
                    value={formatDate(opened.last_validation_at)}
                  />
                  <DetailRow
                    label="Trajanje"
                    value={
                      openedProbe
                        ? `${openedProbe.duration_ms} ms`
                        : "Detalji probe-a nisu trajno sačuvani."
                    }
                  />
                  <DetailRow
                    label="HTTP status"
                    value={detailValue(
                      openedProbe?.http_status,
                      "HTTP status nije trajno sačuvan.",
                    )}
                  />
                  <DetailRow
                    label="Veličina odgovora"
                    value={
                      openedProbe
                        ? `${openedProbe.size_bytes.toLocaleString("sr-RS")} B`
                        : "Veličina nije trajno sačuvana."
                    }
                  />
                  <DetailRow
                    label="XML validan"
                    value={
                      openedProbe?.detected_format === "XML"
                        ? openedProbe.successful
                          ? "DA"
                          : "NE"
                        : openedProbe
                          ? "Nije XML format."
                          : "Rezultat formata nije trajno sačuvan."
                    }
                  />
                </DetailSection>
                <DetailSection title="Last Import">
                  <DetailRow
                    label="Broj proizvoda"
                    value={detailValue(
                      acquisition?.accepted_record_count,
                      "Uspešan import još ne postoji.",
                    )}
                  />
                  <DetailRow
                    label="Broj kategorija"
                    value="Acquisition ne beleži ovu metriku."
                  />
                  <DetailRow
                    label="Broj slika"
                    value="Acquisition ne beleži ovu metriku."
                  />
                  <DetailRow
                    label="Broj opisa"
                    value="Acquisition ne beleži ovu metriku."
                  />
                  <DetailRow
                    label="Encoding"
                    value="Encoding nije deo postojećeg Acquisition DTO-a."
                  />
                </DetailSection>
                <DetailSection title="Schema">
                  <DetailRow label="Postoji" value={schema ? "DA" : "NE"} />
                  {schema ? (
                    <>
                      <DetailRow
                        label="Schema ID"
                        value={String(schema.schema_code ?? schema.id)}
                      />
                      <DetailRow
                        label="Verzija"
                        value={detailValue(schema.version_number, "Nije dostupna.")}
                      />
                      <DetailRow
                        label="Status"
                        value={<StatusChip value={String(schema.status)} />}
                      />
                      <DetailRow
                        label="Field count"
                        value={detailValue(
                          schema.field_count,
                          "Schema postoji ali nije analizirana.",
                        )}
                      />
                      <DetailRow
                        label="Poslednja analiza"
                        value={formatDate(schema.updated_at)}
                      />
                      {Number(schema.field_count ?? 0) === 0 && (
                        <Alert severity="warning">
                          Schema postoji ali nije analizirana.
                        </Alert>
                      )}
                    </>
                  ) : (
                    <Alert severity="info">Schema nije kreirana.</Alert>
                  )}
                </DetailSection>
                <DetailSection title="Mapping">
                  <DetailRow label="Postoji" value={mapping ? "DA" : "NE"} />
                  {mapping ? (
                    <>
                      <DetailRow
                        label="Mapping ID"
                        value={String(mapping.mapping_code ?? mapping.id)}
                      />
                      <DetailRow
                        label="Status"
                        value={<StatusChip value={String(mapping.status)} />}
                      />
                    </>
                  ) : (
                    <Alert severity="info">
                      {schema
                        ? "Mapping nije napravljen."
                        : "Mapping nije moguć dok Schema nije kreirana."}
                    </Alert>
                  )}
                </DetailSection>
                <DetailSection title="Acquisition">
                  <DetailRow label="Postoji" value={acquisition ? "DA" : "NE"} />
                  {acquisition ? (
                    <DetailRow
                      label="Status"
                      value={<StatusChip value={String(acquisition.status)} />}
                    />
                  ) : (
                    <Alert severity="info">
                      {!schema
                        ? "Acquisition nije moguć dok Schema nije kreirana."
                        : !mapping
                          ? "Acquisition nije moguć dok Mapping nije napravljen."
                          : "Acquisition još nije pokrenut."}
                    </Alert>
                  )}
                </DetailSection>
                <DetailSection title="Snapshot">
                  {snapshot ? (
                    <>
                      <DetailRow
                        label="Snapshot ID"
                        value={String(snapshot.snapshot_code ?? snapshot.id)}
                      />
                      <DetailRow
                        label="Datum"
                        value={formatDate(
                          snapshot.finalized_at ?? snapshot.created_at,
                        )}
                      />
                    </>
                  ) : (
                    <Alert severity="info">
                      {acquisition
                        ? "Snapshot još nije kreiran za obrađeni import."
                        : "Snapshot ne postoji jer Acquisition nije završen."}
                    </Alert>
                  )}
                </DetailSection>
                <DetailSection title="Delta">
                  {delta ? (
                    <>
                      <DetailRow
                        label="Poslednji Delta Run"
                        value={String(delta.delta_code ?? delta.id)}
                      />
                      <DetailRow
                        label="Broj izmena"
                        value={
                          Number(delta.added_items ?? 0) +
                          Number(delta.modified_items ?? 0) +
                          Number(delta.removed_items ?? 0)
                        }
                      />
                    </>
                  ) : (
                    <Alert severity="info">
                      {snapshot
                        ? "Delta Run još nije pokrenut."
                        : "Delta nije moguć dok Snapshot ne postoji."}
                    </Alert>
                  )}
                </DetailSection>
              </Stack>
  );
}
