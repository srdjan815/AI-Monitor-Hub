import type { Operation } from "../../types";

export const REQUIRED_TARGETS = new Set(["product_code", "name", "ean", "price"]);

export const TARGETS = [
  { value: "product_code", label: "Šifra artikla dobavljača *", help: "Jedinstvena šifra artikla u cenovniku dobavljača." },
  { value: "ean", label: "Barkod (EAN) *", help: "EAN ili drugi standardni barkod proizvoda." },
  { value: "name", label: "Naziv proizvoda *", help: "Puni naziv proizvoda; može se sastaviti od više izvornih polja." },
  { value: "description", label: "Opis proizvoda", help: "Tekstualni opis proizvoda." },
  { value: "manufacturer", label: "Proizvođač", help: "Naziv proizvođača ili brenda." },
  { value: "manufacturer_part_number", label: "Šifra proizvođača", help: "Kataloška šifra koju daje proizvođač." },
  { value: "category", label: "Kategorija", help: "Kategorija ili grupa proizvoda dobavljača." },
  { value: "price", label: "Cena *", help: "Nabavna ili prodajna cena iz cenovnika." },
  { value: "currency", label: "Valuta", help: "Oznaka valute, na primer RSD ili EUR." },
  { value: "vat_rate", label: "Stopa PDV-a", help: "Procenat poreza na dodatu vrednost." },
  { value: "stock", label: "Količina na stanju", help: "Broj trenutno dostupnih komada." },
  { value: "stock_status", label: "Status dostupnosti", help: "Tekstualna oznaka dostupnosti proizvoda." },
  { value: "image_url", label: "Slika proizvoda", help: "Internet adresa slike proizvoda." },
  { value: "primary_image_url", label: "Glavna slika proizvoda", help: "Glavna internet adresa slike proizvoda." },
  { value: "image_urls", label: "Galerija slika", help: "Lista internet adresa svih slika proizvoda." },
  { value: "product_url", label: "Stranica proizvoda", help: "Internet adresa proizvoda kod dobavljača." },
  { value: "warranty", label: "Garancija", help: "Garantni rok u obliku u kom ga dobavljač dostavlja." }
];

export function suggestedTarget(name: string): string {
  const normalized = name.toLocaleLowerCase("sr-RS").replace(/[^a-z0-9čćžšđ]+/g, "_");
  const suggestions: Array<[RegExp, string]> = [
    [/^(sifra|šifra|sku|code|product_code)$/, "product_code"],
    [/^acproduct$/, "product_code"],
    [/^(barkod|barcode|ean|gtin)$/, "ean"],
    [/^acean$/, "ean"],
    [/^(naziv|name|product_name)$/, "name"],
    [/^acname$/, "name"],
    [/^(opis|description)$/, "description"],
    [/^(acinlinespecification|acproductdescription)$/, "description"],
    [/^(proizvodjac|proizvođač|manufacturer|brand)$/, "manufacturer"],
    [/^acdept$/, "manufacturer"],
    [/^(mpn|manufacturer_part_number|sifra_proizvodjaca)$/, "manufacturer_part_number"],
    [/^(kategorija|category|grupa|nadgrupa)$/, "category"],
    [/^(cena|price|nabavna_cena|veleprodajna_cena)$/, "price"],
    [/^anprice$/, "price"],
    [/^(valuta|currency)$/, "currency"],
    [/^(pdv|vat|vat_rate)$/, "vat_rate"],
    [/^(stanje|stock|kolicina|količina)$/, "stock"],
    [/^anstock$/, "stock"],
    [/^(dostupnost|availability|stock_status)$/, "stock_status"],
    [/^(slika|image|image_url)$/, "image_url"],
    [/^primary_image_url$/, "primary_image_url"],
    [/^image_urls$/, "image_urls"],
    [/^(link|url|product_url)$/, "product_url"],
    [/^(warranty|warrantyterm|warranty_period|garancija|garantni_rok)$/, "warranty"],
    [/^attr_(garancija.*|warranty_term.*)$/, "warranty"],
    [/^acsubcategory$/, "category"]
  ];
  return suggestions.find(([pattern]) => pattern.test(normalized))?.[1] ?? "";
}
export function initialSuggestions(fields: AnalysisField[]): Record<string, string> {
  const used = new Set<string>();
  const result: Record<string, string> = {};
  for (const item of fields) {
    const target = suggestedTarget(item.field.name);
    if (target && !used.has(target)) {
      result[item.field.id] = target;
      used.add(target);
    }
  }
  return result;
}

export interface AnalysisField {
  field: { id: string; name: string; data_type: string; position: number };
  sample_values: string[];
}

export interface StoredAnalysis {
  profile: Operation;
  original_filename?: string | null;
  detected_format: string;
  record_count: number;
  fields: AnalysisField[];
}

export interface MappingTestResult {
  successful: boolean;
  tested_records: number;
  warning_count: number;
  error_count: number;
  message: string;
}

export interface PriceListRecord {
  record_number: number;
  manufacturer_code?: string | null;
  ean?: string | null;
  name?: string | null;
  price?: string | null;
  values: Record<string, string | null>;
}

export function loadAnalysis(): StoredAnalysis | null {
  try {
    const value = localStorage.getItem("amh.schema-analysis");
    return value ? (JSON.parse(value) as StoredAnalysis) : null;
  } catch {
    return null;
  }
}
