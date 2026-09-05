import type { Dispatch, SetStateAction } from "react";
import { CloudDownloadRounded } from "@mui/icons-material";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Step, StepLabel, Stepper } from "@mui/material";

import type { Source, SourceProbeResult } from "../../types";
import type { ConnectionForm } from "./sourceForm";
import { SourceConfigurationStep } from "./SourceConfigurationStep";
import { SourceMethodStep, SourceProbeStep } from "./SourceWizardSteps";

type Props = {
  open: boolean;
  step: number;
  form: ConnectionForm;
  draft: Source | null;
  probe: SourceProbeResult | null;
  probeFile: File | null;
  certificateFile: File | null;
  networkSupported: boolean;
  portalReady: boolean;
  certificateReady: boolean;
  savingDraft: boolean;
  testingConnection: boolean;
  activating: boolean;
  onClose: () => void;
  setStep: Dispatch<SetStateAction<number>>;
  onUpdate: (key: keyof ConnectionForm, value: string | boolean) => void;
  onAuthenticationType: (value: string) => void;
  onSoapProfile: (value: string) => void;
  onIntegrationProfile: (value: string) => void;
  setProbeFile: Dispatch<SetStateAction<File | null>>;
  setCertificateFile: Dispatch<SetStateAction<File | null>>;
  onSaveDraft: () => void;
  onTestConnection: () => void;
  onActivate: (source: Source) => void;
};

export function SourceWizardDialog({ open: wizardOpen, step, form, draft, probe, probeFile, certificateFile, networkSupported, portalReady, certificateReady, savingDraft, testingConnection, activating, onClose, setStep, onUpdate: update, onAuthenticationType: selectAuthenticationType, onSoapProfile: selectSoapProfile, onIntegrationProfile: selectIntegrationProfile, setProbeFile, setCertificateFile, onSaveDraft, onTestConnection, onActivate }: Props) {
  return (
    <Dialog
            open={wizardOpen}
        onClose={onClose}
            fullWidth
            maxWidth="md"
          >
            <DialogTitle>Povezivanje dobavljača sa cenovnikom</DialogTitle>
            <DialogContent>
              <Stepper activeStep={step} sx={{ py: 2 }}>
                {[
                  "Način preuzimanja",
                  "Podaci",
                  "Probno preuzimanje",
                  "Aktivacija",
                ].map((label) => (
                  <Step key={label}>
                    <StepLabel>{label}</StepLabel>
                  </Step>
                ))}
              </Stepper>
              {step === 0 && <SourceMethodStep form={form} onUpdate={update} />}
          {step === 1 && (
            <SourceConfigurationStep
              form={form}
              networkSupported={networkSupported}
              probeFile={probeFile}
              certificateFile={certificateFile}
              onUpdate={update}
              onAuthenticationType={selectAuthenticationType}
              onSoapProfile={selectSoapProfile}
              onIntegrationProfile={selectIntegrationProfile}
              setProbeFile={setProbeFile}
              setCertificateFile={setCertificateFile}
            />
          )}
          {step === 2 && probe && <SourceProbeStep probe={probe} />}
          {step === 3 && (
                <Alert severity="success">
                  Konekcija je aktivna. Sledeći koraci su podešavanje Schema i
                  Mapping profila.
                </Alert>
              )}
            </DialogContent>
            <Divider />
            <DialogActions>
          <Button onClick={onClose}>Zatvori</Button>
              {step === 0 && (
                <Button variant="contained" onClick={() => setStep(1)}>
                  Nastavi
                </Button>
              )}
              {step === 1 && (
                <>
                  <Button
                    onClick={() => onSaveDraft()}
                    disabled={
                      !form.name.trim() || !portalReady || savingDraft
                    }
                  >
                    Sačuvaj kao nacrt
                  </Button>
                  {networkSupported || form.method === "MANUAL_UPLOAD" ? (
                    <Button
                      variant="contained"
                      startIcon={<CloudDownloadRounded />}
                      onClick={() => onTestConnection()}
                      disabled={
                        !form.name.trim() ||
                        !portalReady ||
                        !certificateReady ||
                        testingConnection ||
                        (form.method === "MANUAL_UPLOAD" && !probeFile)
                      }
                    >
                      {form.method === "MANUAL_UPLOAD"
                        ? "Probno učitaj fajl"
                        : "Probno preuzmi cenovnik"}
                    </Button>
                  ) : (
                    <Button
                      variant="contained"
                      onClick={() => onSaveDraft()}
                      disabled={!form.name.trim()}
                    >
                      Sačuvaj nacrt
                    </Button>
                  )}
                </>
              )}
              {step === 2 && draft && (
                <Button
                  variant="contained"
                  disabled={!probe?.successful || activating}
                  onClick={() => onActivate(draft)}
                >
                  Aktiviraj konekciju
                </Button>
              )}
            </DialogActions>
          </Dialog>
  );
}
