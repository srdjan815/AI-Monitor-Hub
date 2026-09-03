# Supplier Schema Profiles — Chapter 3.3

## Granica poglavlja

Schema Profile je verzionisan opis strukture podataka jednog Supplier Source
Connection-a. Čuva isključivo metadata polja: naziv, logičku poziciju, očekivani
tip, logičku putanju i semantičke oznake. Ne sadrži dobavljačke proizvode niti
izvršava preuzimanje, parsiranje, automatsko otkrivanje, mapiranje, normalizaciju,
uvoz, snapshot ili delta obradu.

## Model verzionisanja

Svaki `supplier_schema_profiles` zapis predstavlja jednu nepromenljivu verziju.
`schema_code` se generiše iz posebne PostgreSQL sekvence u formatu `SCH-000001`.
Nova struktura nastaje kloniranjem postojeće verzije u novi `DRAFT`; aktivne i
arhivirane verzije se ne menjaju. Klon kopira samo metadata polja.

Statusi su:

- `DRAFT` — jedina verzija kojoj se mogu menjati profil i polja;
- `ACTIVE` — trenutno važeći opis strukture Source Connection-a;
- `ARCHIVED` — istorijska, čitljiva i nepromenljiva verzija.

Parcijalni jedinstveni indeks garantuje najviše jednu aktivnu verziju po Source
Connection-u. Aktivacija nove verzije u istoj transakciji arhivira prethodnu.
`is_active=false` predstavlja soft delete i ne briše istoriju.

## Schema Field

`supplier_schema_fields` pripada tačno jednoj verziji profila. `path` je samo
logička lokacija, na primer `column 5`, `Sheet1!B7`,
`/products/product/price` ili `products[].price`; nikada se ne evaluira.

Podržani tipovi su `STRING`, `INTEGER`, `DECIMAL`, `BOOLEAN`, `DATE`,
`DATETIME`, `TIME`, `UUID`, `EMAIL`, `URL`, `PHONE`, `JSON`, `ENUM` i
`BINARY`. Validacija odbija duplikate šifre i pozicije, više ključnih polja,
više cenovnih polja, neispravne putanje, nedozvoljene length/precision/scale
kombinacije i kontradikciju `required=true` sa `nullable=true`.

## Transakcije i dozvole

Sloj ostaje `Router → Service → Repository → SQLAlchemy`. Repository samo
mutira i poziva `flush`; servis je vlasnik `commit`, `rollback` i `refresh`
operacija. Optimističke `version` kolone štite profil i polje od izgubljenih
izmena.

Dozvole su:

- `schema_profiles.read`;
- `schema_profiles.write`;
- `schema_profiles.activate`.

OpenAPI grupa je `supplier-schema-profiles`, sa srpskim opisima verzije, polja,
tipa, putanje, aktivacije i istorijskih verzija.

## Namerno odloženo

Nema mrežnog pristupa, fajlova, parsera, preview-a, import poslova, automatskog
schema discovery/inference procesa, mapping pravila, snapshot-a, delti,
schedulera ili worker-a. Te sposobnosti ne pripadaju Chapter 3.3.
