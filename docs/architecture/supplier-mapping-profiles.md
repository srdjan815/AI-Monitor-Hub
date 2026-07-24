# Supplier Mapping Profiles — Chapter 3.4

## Granica odgovornosti

Mapping Profile opisuje kako se postojeći `SupplierSchemaField` povezuje sa
logičkim nazivom internog Catalog atributa. Profil i pravila su isključivo
deklarativna konfiguracija. Modul ne pristupa Catalog kodu ili repository-ju,
ne parsira dobavljačke podatke i ne izvršava transformacije, validacije, uvoz,
snapshot, delta ili background posao.

## Verzije

Svaki `supplier_mapping_profiles` zapis je jedna nepromenljiva verzija za tačno
jedan `SupplierSchemaProfile`. `mapping_code` nastaje iz posebne PostgreSQL
sekvence u formatu `MAP-000001`. Statusi su `DRAFT`, `ACTIVE` i `ARCHIVED`.

Samo DRAFT verzija može menjati profil i pravila. Clone kopira aktivna pravila
u novu DRAFT verziju, dok izvorna verzija ostaje nepromenjena. Parcijalni
jedinstveni indeks dozvoljava najviše jednu ACTIVE Mapping Profile verziju po
Schema Profile-u. Aktivacija nove verzije u istoj transakciji arhivira
prethodnu.

ACTIVE Mapping Profile je dozvoljen samo uz ACTIVE i nesakriven Schema Profile.
Kada Chapter 3.3 arhivira ili soft-delete-uje Schema Profile, povezana aktivna
verzija mapiranja se arhivira u istoj transakciji. Istorijska mapiranja ostaju
čitljiva.

## Mapping Rule

Pravilo direktno referencira postojeći `supplier_schema_fields` zapis i čuva:

- logički `target_attribute`, bez Catalog FK-a ili Catalog importa;
- deklarativni `transformation_type` i ograničeni JSON
  `transformation_config`;
- `required`, `default_value`, `validation_rule` i jedinstveni `priority`.

`default_value` i `validation_rule` koriste PostgreSQL `TEXT`, pa veliki opisi,
tehničke specifikacije i HTML sadržaj ne zahtevaju buduću promenu šeme. API
koristi postojeći veliki Foundation content limit radi zaštite request granice.

Jedan aktivni Mapping Profile ne može dva puta mapirati isto Schema Field polje,
isti target atribut ili isti prioritet. Reference na drugi profil ili
soft-deleted Schema Field se odbijaju.

Podržane deklaracije transformacije su `NONE`, `COPY`, `DEFAULT_VALUE`,
`CONSTANT`, `CONCAT`, `SPLIT`, `TRIM`, `UPPERCASE`, `LOWERCASE`, `REPLACE` i
`REGEX`. Njihovo izvršenje izričito nije deo Chapter 3.4.

## Arhitektura i bezbednost

Tok ostaje `Router → Service → Repository → SQLAlchemy`. Repository samo poziva
`flush`; servis poseduje `commit`, `rollback` i `refresh`. Profil i pravilo
imaju nezavisne optimističke verzije.

Dozvole su:

- `mapping_profiles.read`;
- `mapping_profiles.write`;
- `mapping_profiles.activate`.

OpenAPI grupa `supplier-mapping-profiles` koristi srpske opise za profil,
pravilo, ciljni atribut, transformaciju, verzionisanje i aktivaciju.

## Namerno odloženo

Nema import execution-a, parsera, mrežnih poziva, schedulera, worker-a,
preview-a, automatskog ili AI mapiranja, transformacionog runtime-a, snapshot-a,
delta obračuna, incidenata niti Catalog upisa. Mapping Profile i Mapping Rule
su stabilan konfiguracioni ugovor koji Chapter 3.5 može direktno čitati.
