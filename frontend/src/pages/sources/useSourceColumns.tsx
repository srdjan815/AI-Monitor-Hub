import { useMemo } from "react";
import { Typography } from "@mui/material";

import type { Column } from "../../components/EntityTable";
import { StatusChip } from "../../components/StatusChip";
import type { Source } from "../../types";
import { displayFormat, displayMethod } from "./sourceDisplay";

export function useSourceColumns(supplierNames: ReadonlyMap<string, string>): Column<Source>[] {
  return useMemo(() => [
    { key: "supplier", label: "Dobavljač", tooltip: "Dobavljač kome konekcija pripada.", render: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id, csv: (row) => supplierNames.get(row.supplier_id) ?? row.supplier_id },
    { key: "name", label: "Konekcija", tooltip: "Naziv načina na koji dobavljač isporučuje cenovnik.", render: (row) => <Typography fontWeight={650}>{row.name}</Typography>, csv: (row) => row.name },
    { key: "source_type", label: "Način preuzimanja", tooltip: "Kanal kojim cenovnik dolazi u sistem.", render: displayMethod, csv: displayMethod },
    { key: "format", label: "Format", tooltip: "Očekivani format dobavljačkog cenovnika.", render: displayFormat, csv: displayFormat },
    { key: "status", label: "Status", tooltip: "Nacrt, aktivna konekcija ili arhiviran zapis.", render: (row) => <StatusChip value={row.is_active ? row.status : "ARCHIVED"} />, csv: (row) => row.status },
    { key: "validation", label: "Poslednji test", tooltip: "Rezultat poslednjeg probnog preuzimanja.", render: (row) => <StatusChip value={row.last_validation_status === "VALID" ? "READY" : row.last_validation_status === "INVALID" ? "FAILED" : "PENDING"} />, csv: (row) => row.last_validation_status },
  ], [supplierNames]);
}
