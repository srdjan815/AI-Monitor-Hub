import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AddRounded, ArchiveRounded, EditRounded } from "@mui/icons-material";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import toast from "react-hot-toast";
import { supplierApi } from "../api/supplierApi";
import { DetailDrawer } from "../components/DetailDrawer";
import { EntityTable, type Column } from "../components/EntityTable";
import { ErrorBlock } from "../components/AsyncState";
import { PageHeader } from "../components/PageHeader";
import { RecordDetails } from "../components/RecordDetails";
import { StatusChip } from "../components/StatusChip";
import { useAuth } from "../state/AuthContext";
import { useWorkspace } from "../state/WorkspaceContext";
import type { ApiError, Supplier } from "../types";

const emptyForm = {
  company_name: "",
  address: "",
  tax_identifier: "",
  registration_number: "",
  status: "ACTIVE"
};

const emptyContactForm = {
  contact_type: "GENERAL",
  name: "",
  email: "",
  phone: "",
  position: "",
  is_primary: true
};

export function SuppliersPage() {
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [opened, setOpened] = useState<Supplier | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [contactForm, setContactForm] = useState(emptyContactForm);
  const auth = useAuth();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const suppliers = useQuery({
    queryKey: ["suppliers", page, query],
    queryFn: () =>
      supplierApi.suppliers({
        limit: 25,
        offset: page * 25,
        active_only: false,
        company_name: query || undefined
      }),
    placeholderData: (previous) => previous
  });
  const save = useMutation({
    mutationFn: async () => {
      if (opened) {
        return supplierApi.updateSupplier(opened.id, {
          ...form,
          version: opened.version
        });
      }
      const supplier = await supplierApi.createSupplier(form);
      const hasContact = [
        contactForm.name,
        contactForm.email,
        contactForm.phone,
        contactForm.position
      ].some((value) => value.trim());
      if (hasContact) {
        try {
          await supplierApi.createContact(supplier.id, {
            ...contactForm,
            email: contactForm.email.trim() || null,
            phone: contactForm.phone.trim() || null,
            position: contactForm.position.trim() || null
          });
        } catch (error) {
          const apiError = error as ApiError;
          toast.error(
            `Dobavljač je kreiran, ali kontakt nije sačuvan: ${apiError.message}`
          );
        }
      }
      return supplier;
    },
    onSuccess: (row) => {
      toast.success(opened ? "Dobavljač je izmenjen." : "Dobavljač je kreiran.");
      setOpened(row);
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => supplierApi.deactivateSupplier(id),
    onSuccess: () => {
      toast.success("Dobavljač je deaktiviran.");
      setOpened(null);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error: ApiError) => toast.error(`${error.code}: ${error.message}`)
  });
  const columns = useMemo<Column<Supplier>[]>(
    () => [
      {
        key: "supplier_code",
        label: "Šifra",
        tooltip: "Nepromjenljiva interna šifra dobavljača.",
        sortable: true,
        render: (row) => <Typography fontFamily="monospace">{row.supplier_code}</Typography>,
        csv: (row) => row.supplier_code
      },
      {
        key: "company_name",
        label: "Poslovni naziv",
        tooltip: "Puni poslovni naziv dobavljača.",
        sortable: true,
        width: 240,
        render: (row) => <Typography fontWeight={650}>{row.company_name}</Typography>,
        csv: (row) => row.company_name
      },
      {
        key: "status",
        label: "Operativni status",
        tooltip: "Poslovno stanje dobavljača, nezavisno od arhiviranja zapisa.",
        render: (row) => <StatusChip value={row.status} />,
        csv: (row) => row.status
      },
      {
        key: "is_active",
        label: "Lifecycle",
        tooltip: "Aktivan zapis može da se menja; arhivirani zapis je zaključan.",
        render: (row) => (
          <StatusChip value={row.is_active ? "ACTIVE" : "ARCHIVED"} />
        ),
        csv: (row) => (row.is_active ? "ACTIVE" : "ARCHIVED")
      },
      {
        key: "tax_identifier",
        label: "PIB",
        tooltip: "Poreski identifikacioni broj.",
        render: (row) => row.tax_identifier || "—",
        csv: (row) => row.tax_identifier
      },
      {
        key: "updated_at",
        label: "Izmenjeno",
        tooltip: "Vreme poslednje potvrđene izmene.",
        sortable: true,
        render: (row) => new Date(row.updated_at).toLocaleString("sr-RS"),
        csv: (row) => row.updated_at
      }
    ],
    []
  );
  const edit = () => {
    if (!opened) return;
    setForm({
      company_name: opened.company_name,
      address: opened.address ?? "",
      tax_identifier: opened.tax_identifier ?? "",
      registration_number: opened.registration_number ?? "",
      status: opened.status
    });
    setFormOpen(true);
  };
  const contactStarted = [
    contactForm.name,
    contactForm.email,
    contactForm.phone,
    contactForm.position
  ].some((value) => value.trim());
  const contactInvalid =
    !opened &&
    contactStarted &&
    (!contactForm.name.trim() ||
      (!contactForm.email.trim() && !contactForm.phone.trim()));
  return (
    <>
      <PageHeader
        title="Dobavljači"
        description="Registracija, status, kontaktni identitet i operativni radni prostor."
        actions={
          auth.can("suppliers.write") && (
            <Tooltip title="Registruj novog dobavljača; backend dodeljuje internu šifru.">
              <Button
                variant="contained"
                startIcon={<AddRounded />}
                onClick={() => {
                  setOpened(null);
                  setForm(emptyForm);
                  setContactForm(emptyContactForm);
                  setFormOpen(true);
                }}
              >
                Dodaj dobavljača
              </Button>
            </Tooltip>
          )
        }
      />
      <TextField
        size="small"
        label="Pretraga po poslovnom nazivu"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setPage(0);
        }}
        sx={{ mb: 2, width: { xs: "100%", sm: 360 } }}
      />
      {suppliers.isError && <ErrorBlock error={suppliers.error} retry={() => suppliers.refetch()} />}
      <EntityTable
        tableId="suppliers"
        columns={columns}
        rows={suppliers.data?.items ?? []}
        total={suppliers.data?.total ?? 0}
        page={page}
        pageSize={25}
        loading={suppliers.isLoading}
        selected={selected}
        onSelected={setSelected}
        onPage={setPage}
        onOpen={(row) => {
          setOpened(row);
          workspace.setSupplierId(row.id);
        }}
        onRefresh={() => suppliers.refetch()}
      />
      <DetailDrawer
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={opened?.company_name ?? ""}
        subtitle={opened?.supplier_code}
        actions={
          auth.can("suppliers.write") && opened?.is_active ? (
            <>
              <Button startIcon={<EditRounded />} onClick={edit}>Izmeni</Button>
              <Button
                color="warning"
                startIcon={<ArchiveRounded />}
                onClick={() => {
                  if (confirm("Arhivirati dobavljača? Zapis nakon toga nije moguće menjati niti vratiti kroz postojeći API.")) {
                    deactivate.mutate(opened.id);
                  }
                }}
              >
                Arhiviraj
              </Button>
            </>
          ) : undefined
        }
      >
        {opened && <RecordDetails record={opened as unknown as Record<string, unknown>} />}
      </DetailDrawer>
      <Dialog open={formOpen} onClose={() => setFormOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{opened ? "Izmeni dobavljača" : "Novi dobavljač"}</DialogTitle>
        <DialogContent>
          <Stack gap={2} mt={1}>
            {[
              ["company_name", "Poslovni naziv", "Zvanični naziv pravnog lica."],
              ["address", "Adresa", "Poslovna adresa dobavljača."],
              ["tax_identifier", "PIB", "Poreski identifikacioni broj."],
              ["registration_number", "Matični broj", "Registracioni ili matični broj."]
            ].map(([key, label, helper]) => (
              <TextField
                key={key}
                label={label}
                value={form[key as keyof typeof form]}
                required={key === "company_name"}
                helperText={helper}
                onChange={(event) =>
                  setForm((value) => ({ ...value, [key]: event.target.value }))
                }
              />
            ))}
            <FormControl>
              <InputLabel id="supplier-status-label">Status</InputLabel>
              <Select
                labelId="supplier-status-label"
                label="Status"
                value={form.status}
                onChange={(event) =>
                  setForm((value) => ({ ...value, status: event.target.value }))
                }
              >
                <MenuItem value="ACTIVE">Aktivan</MenuItem>
                <MenuItem value="INACTIVE">Neaktivan</MenuItem>
                <MenuItem value="SUSPENDED">Suspendovan</MenuItem>
              </Select>
            </FormControl>
            {!opened && (
              <>
                <Typography variant="h6" mt={1}>
                  Primarni kontakt (opciono)
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Kontakt se čuva kroz postojeći Supplier Contact API.
                </Typography>
                <FormControl>
                  <InputLabel id="contact-type-label">Vrsta kontakta</InputLabel>
                  <Select
                    labelId="contact-type-label"
                    label="Vrsta kontakta"
                    value={contactForm.contact_type}
                    onChange={(event) =>
                      setContactForm((value) => ({
                        ...value,
                        contact_type: event.target.value
                      }))
                    }
                  >
                    <MenuItem value="GENERAL">Opšti</MenuItem>
                    <MenuItem value="TECHNICAL">Tehnički</MenuItem>
                    <MenuItem value="COMMERCIAL">Komercijalni</MenuItem>
                    <MenuItem value="BILLING">Fakturisanje</MenuItem>
                    <MenuItem value="OTHER">Ostalo</MenuItem>
                  </Select>
                </FormControl>
                {[
                  ["name", "Ime i prezime", "Ime kontakt osobe."],
                  ["email", "Email", "Email adresa kontakt osobe."],
                  ["phone", "Telefon", "Broj telefona kontakt osobe."],
                  ["position", "Pozicija", "Funkcija kontakt osobe kod dobavljača."]
                ].map(([key, label, helper]) => (
                  <TextField
                    key={key}
                    label={label}
                    value={contactForm[key as keyof typeof contactForm]}
                    helperText={helper}
                    onChange={(event) =>
                      setContactForm((value) => ({
                        ...value,
                        [key]: event.target.value
                      }))
                    }
                  />
                ))}
                <FormControlLabel
                  control={
                    <Switch
                      checked={contactForm.is_primary}
                      onChange={(event) =>
                        setContactForm((value) => ({
                          ...value,
                          is_primary: event.target.checked
                        }))
                      }
                    />
                  }
                  label="Primarni kontakt"
                />
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFormOpen(false)}>Otkaži</Button>
          <Button
            variant="contained"
            onClick={() => save.mutate()}
            disabled={
              save.isPending || !form.company_name.trim() || contactInvalid
            }
          >
            Sačuvaj
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
