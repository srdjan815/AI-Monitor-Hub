# Supplier API — Chapter 3.9

## Svrha i granice

Chapter 3.9 konsoliduje postojeći Supplier Platform API za budući Admin UI.
Ne uvodi novi domen, poslovna pravila, tabelu, worker, raspored, notification
mehanizam niti Catalog/Inventory upis. Kanonski API ostaje verzionisan pod
`/api/v1`, a poslovna hijerarhija ostaje pod `/api/v1/suppliers`.

Postojeći tok ostaje `Router → Service → Repository → SQLAlchemy →
PostgreSQL`. Konsolidacioni servis samo sastavlja bezbedne agregate i poziva
postojeće Incident servise.

## Grupe resursa

- Supplier i Contact: `/api/v1/suppliers`
- Source Connections: `/api/v1/suppliers/{supplier_id}/sources`
- Schema Profiles i Fields: `.../schema-profiles`
- Mapping Profiles i Rules: `.../mapping-profiles`
- Acquisition Runs, Records i Issues: `.../acquisitions`
- Snapshots, Items i archive operacije: `.../snapshots`
- Delta Runs, Items i Field Changes: `.../deltas`
- Konsolidacioni pregled i pretraga: `/api/v1/suppliers/platform`
- Kanonski kompletan Incident API:
  `/api/v1/suppliers/platform/supplier-incidents`
- Kanonska lagana Incident lista:
  `/api/v1/suppliers/platform/incidents`

## Kompatibilnost i deprecacija

Deprecated rute ostaju funkcionalne u API v1. OpenAPI ih označava sa
`deprecated=true`; opis i ova matrica navode zamenu. Uklanjanje zahteva novu
glavnu API verziju ili posebno odobreno migraciono izdanje. Nema tihog
uklanjanja i nema promene poslovnog ponašanja.

| Postojeća ruta | Preferirana ruta | Status | Dozvola | Odgovor |
|---|---|---|---|---|
| `/supplier-incidents` | `/suppliers/platform/supplier-incidents` | deprecated | `incidents.read/create` | postojeći Incident DTO |
| `/supplier-incidents/{id}/...` | `/suppliers/platform/supplier-incidents/{id}/...` | deprecated | odgovarajuća Incident workflow dozvola | postojeći Incident DTO |
| `/supplier-incidents/sync/...` | `/suppliers/platform/supplier-incidents/sync/...` | deprecated | `incidents.create` | postojeći sync DTO |
| `/supplier-incident-rules` | `/suppliers/platform/supplier-incident-rules` | deprecated | `incident_rules.read/manage` | postojeći Rule DTO |
| `/suppliers/platform/incidents` | isto | canonical | `incidents.read` | `SupplierApiPage` |
| `/suppliers/platform/search` | isto | canonical | `supplier_platform.search` | bezbedni typed rezultati |
| `/suppliers/platform/overview` | isto | canonical | `supplier_platform.overview` | permission-aware agregati |

Ostale Supplier rute su već kanonske ispod `/suppliers` i nemaju alias.

## Paginacija, sortiranje i filtriranje

Kanonska Incident kolekcija vraća `items`, `total`, `limit`, `offset` i
`has_more`. `limit` je 1–100 po podrazumevanoj konfiguraciji, `offset` je
nenegativan i ograničen Foundation limitom. Redosled uvek ima UUID kao
sekundarni tie-breaker.

`sort_by` je allowlist: `created_at`, `updated_at`, `incident_code`,
`severity`, `priority`, `status`, `due_at`; `sort_order` je `asc` ili `desc`.
Filteri podržavaju Supplier, Source Connection, status, severity, priority,
assignee i vremenski opseg. Obrnut vremenski opseg vraća `VALIDATION_ERROR`.
Generička pretraga ne čita Incident opis, correlation context, source fajlove,
`raw_data`, `mapped_data`, Snapshot payload ili Delta dokaze.

## Greške i identifikatori zahteva

Kompatibilna polja `detail`, `code` i `request_id` ostaju. Kanonski envelope
dodaje:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Bezbedna poruka",
    "details": null,
    "field_errors": []
  },
  "request_id": "...",
  "correlation_id": "..."
}
```

Foundation generiše request ID kada bezbedan dolazni `X-Request-ID` ne postoji.
`X-Correlation-ID` prihvata najviše 128 ASCII slova, cifara i znakove
`._:-`; nevalidna vrednost se bezbedno zamenjuje request ID-em. Oba
identifikatora se vraćaju u headerima, ulaze u strukturisane logove i nisu
autentikacioni podatak. Neočekivane greške se bez stack trace-a mapiraju na
`INTERNAL_ERROR`.

## Globalna pretraga i pregled

Pretraga zahteva 2–100 znakova, vraća najviše 50 rezultata i obuhvata samo
bezbedne šifre/nazive za domene koje principal sme da čita. Egzaktna šifra ima
prednost, zatim rezultat deterministički uređuju šifra i UUID.

Pregled je ograničen na najviše 366 dana. Count je `null` i
`permitted=false` kada korisnik nema read dozvolu za domen. Poslednje
operacije i greške su ograničene na po deset zapisa i ne učitavaju item
payload-e.

## Bulk ugovor

Chapter 3.9 izlaže samo:

- `/suppliers/platform/bulk/incidents/assign`
- `/suppliers/platform/bulk/incidents/priority`

Najviše 50 stavki se obrađuje sinhrono. Svaka jedinstvena stavka koristi
postojeći Incident servis i sopstveni commit/rollback; zato odgovor iskreno
prikazuje parcijalni uspeh. Duplikati su `SKIPPED`. Odgovor sadrži
`requested_count`, `succeeded_count`, `failed_count`, `skipped_count` i
bezbedan rezultat svake stavke. Nema generičkog bulk update-a, job-a, queue-a,
rasporeda ni skrivenog Catalog upisa.

## Dozvole, audit i limiti

Postojeći RBAC ostaje jedini izvor dozvola. Search/overview zahtevaju
`supplier_platform.search` odnosno `supplier_platform.overview`, a zatim
filtriraju svaki domen njegovom postojećom read dozvolom. Bulk koristi
`incidents.assign` odnosno `incidents.manage`. Incident Event ostaje
nepromenljivi domenski audit; request/correlation ID i actor ostaju u
Foundation API logu bez kompletnog body-ja.

Foundation request-size i rate-limit middleware ostaju aktivni. Chapter 3.9
ne uvodi procesni limiter. Deployment nastavlja da koristi postojeći deljeni
Redis limiter.

## Detalj naspram liste

Liste ne vraćaju raw/mapped podatke, kompletan Snapshot Item, Delta evidence,
Incident tehnički kontekst, archive manifest ili dugačke opise. Postojeći
zaštićeni detail endpoint-i ostaju jedino mesto za već podržane detalje.

## Migraciona odluka i Chapter 3.10 ugovor

Nije potrebna baza ni Alembic migracija; head ostaje `a6b7c8d9e0f1`.
Chapter 3.10 Admin UI treba da koristi kanonske rute, standardni page/error
envelope, OpenAPI DTO-e i permission-aware `overview`/`search`. UI, frontend
lokalizacija, notifications, scheduling, eksterni API ključevi, GraphQL i
public developer portal nisu deo Chapter 3.9.
