# ADR-001: Supplier Pipeline

- Status: Accepted — Stable v1.0
- Date: 2026-07-28
- Scope: Supplier Platform
- Decision owners: AI Monitor Hub architecture team

## Context

Dobavljači isporučuju cenovnike kroz različite kanale i formate. Sistem mora
proverljivo da pribavi podatke, zaustavi obradu kada se struktura promeni,
normalizuje validne zapise i objavi samo utvrđene promene narednim modulima.
Pri tome dobavljački podaci ne smeju direktno menjati Product ili Catalog.

## Decision

Supplier Pipeline je jedan bounded context sa jasno odvojenim fazama. Svaka
faza koristi rezultat prethodne faze i ne preuzima njenu odgovornost. Trenutna
stabilna implementacija završava se Delta Detection fazom. Canonical Products i
Catalog su downstream granice i nisu odgovornost Supplier Platforme.

## Svrha modula

Supplier Pipeline rešava:

- administraciju dobavljača i njihovih izvora;
- bezbedno povezivanje sa dobavljačkim cenovnikom;
- proveru dostupnosti izvora bez pokretanja importa;
- verzionisanje očekivane strukture izvora;
- mapiranje dobavljačkih polja u stabilan staging oblik;
- kontrolisan Acquisition i očuvanje validnog dobavljačkog stanja;
- poređenje uzastopnih validnih stanja;
- objavljivanje detektovanih promena downstream modulima.

Ne kreira Canonical Product, ne menja Catalog i ne upisuje količine ili cene u
Product.

## Glavni tok

```text
+--------------------+
| Supplier           |
+---------+----------+
          |
          v
+--------------------+
| Connection         |
+---------+----------+
          |
          v
+--------------------+
| Probe              |
+---------+----------+
          |
          v
+--------------------+
| Schema Profile     |
+---------+----------+
          |
          v
+--------------------+
| Mapping Profile    |
+---------+----------+
          |
          v
+--------------------+
| Acquisition        |
+---------+----------+
          |
          v
+--------------------+
| Snapshot           |
+---------+----------+
          |
          v
+--------------------+
| Delta Detection    |  <-- kraj Supplier Platform v1.0
+---------+----------+
          |
          v
+--------------------+
| Canonical Products |  <-- budući downstream modul
+---------+----------+
          |
          v
+--------------------+
| Catalog            |  <-- postojeći vlasnik kanonskih proizvoda
+--------------------+
```

Praktično pravilo: Supplier Pipeline objavljuje činjenice o dobavljačkom
proizvodu i njegovim promenama. Downstream modul odlučuje da li i kako se te
činjenice povezuju sa Canonical Product zapisom.

## Odgovornosti i granice modula

### Supplier

Odgovoran je za:

- stabilan, interni i nepromenljiv Supplier ID;
- poslovni identitet dobavljača;
- kontakte, status i administrativne podatke;
- vlasništvo nad svojim Connection zapisima.

Sme da administrira dobavljača i njegove kontakte.

Ne sme da:

- čuva Product, zalihu ili cenovnik;
- preuzima spoljne fajlove;
- izvršava mapiranje;
- menja Catalog.

### Connection

Odgovoran je za:

- opis kanala pristupa dobavljaču;
- javnu transportnu konfiguraciju;
- referencu na kredencijale;
- izbor adaptera;
- status konfiguracije i rezultat poslednjeg Probe-a.

Sme da:

- pristupi dobavljačkom endpointu preko podržanog adaptera;
- primeni autentikaciju kroz Secret Provider;
- pokrene Probe;
- bude aktiviran tek posle uspešnog Probe-a.

Ne sme da:

- čuva tajne u `configuration` JSON-u;
- tumači poslovnu strukturu cenovnika;
- mapira dobavljačka polja;
- kreira Acquisition Run, Snapshot ili Catalog Product.

### Probe

Odgovoran je samo za proveru da li se izvoru može pristupiti i da li vraćeni
sadržaj izgleda kao podržan cenovnik.

Probe:

- proverava transport i dostupnost kredencijala;
- preuzima probni sadržaj ili prima probni Manual Upload;
- odbija prazan, HTML ili neispravan sadržaj;
- prepoznaje XML, CSV, JSON ili XLSX;
- prikazuje format, veličinu, približan broj i sanitizovan pregled do deset
  zapisa;
- pamti samo rezultat poslednje provere na postojećem Connection zapisu.

Probe izričito:

- ne kreira Acquisition Run;
- ne kreira Snapshot;
- ne menja Catalog;
- ne zahteva Schema Profile;
- ne zahteva Mapping Profile;
- ne objavljuje podatke downstream modulima.

### Schema Profile

Odgovoran je za:

- verzionisani opis očekivane strukture izvora;
- root path i item path kada ih format zahteva;
- definicije, tipove i obaveznost source polja;
- zaustavljanje importa kada struktura više ne odgovara aktivnom profilu.

Sme da potvrdi ili odbije strukturu pribavljenog izvora.

Ne sme da:

- preuzima podatke;
- čuva kredencijale;
- definiše poslovni prevod u kanonska polja;
- menja Catalog.

### Mapping Profile

Odgovoran je za:

- verzionisano prevođenje dobavljačkih polja u stabilna staging polja;
- transformacije koje su eksplicitno podržane pravilima mapiranja;
- vezu sa konkretnom verzijom Schema Profile-a.

Sme da transformiše samo već pribavljene i schema-validne vrednosti.

Ne sme da:

- pristupa dobavljaču;
- preuzima fajl;
- menja izvornu Schema definiciju;
- kreira Canonical Product;
- upisuje u Catalog.

### Acquisition

Odgovoran je za:

- stvarno pribavljanje sadržaja preko aktivnog Connection-a ili Manual Upload-a;
- proveru aktivnog Supplier, Connection, Schema i Mapping konteksta;
- očuvanje artefakta i checksum-a prema postojećoj storage strategiji;
- schema validaciju i mapiranje;
- staged zapise, issues, statistiku i terminalni status run-a;
- transakcije, idempotency i bezbedne poslovne greške.

Sme da proizvede validiran i mapiran staging rezultat koji Snapshot Engine može
da koristi.

Ne sme da:

- podešava Connection, Schema ili Mapping;
- prikriva schema grešku i nastavi obradu;
- direktno kreira Snapshot u Probe toku;
- kreira Canonical Product;
- menja Catalog.

Snapshot je posebna faza. Acquisition priprema proverene ulazne činjenice;
Snapshot Engine iz njih eksplicitno gradi novo validno stanje.

### Snapshot

Odgovoran je za:

- najnovije validno dobavljačko stanje;
- immutable skup Supplier Product Snapshot stavki;
- vezu sa uspešnim Acquisition Run-om;
- checksum, statistiku, arhiviranje i proveru integriteta;
- aktivaciju novog stanja tek nakon uspešne validacije.

Sme da zameni aktivni Snapshot samo novim potpuno validnim Snapshot-om.

Ne sme da:

- menja prethodni aktivni Snapshot tokom neuspele obrade;
- ponovo preuzima source sadržaj;
- podešava Schema ili Mapping;
- kreira Canonical Product ili menja Catalog.

### Delta Detection

Odgovoran je za:

- poređenje novog validnog Snapshot-a sa prethodnim aktivnim Snapshot-om;
- ADDED, MODIFIED, REMOVED i UNCHANGED klasifikaciju;
- promene po poljima i agregirani sažetak;
- immutable rezultat poređenja;
- objavljivanje samo detektovanih promena downstream potrošačima.

Ne sme da:

- menja Snapshot stavke;
- ponovo izvršava Acquisition;
- odlučuje koji Canonical Product odgovara dobavljačkom proizvodu;
- menja Catalog.

### Canonical Products

Ovo je budući downstream modul, a ne deo Supplier Platform v1.0.

Biće odgovoran za:

- matching dobavljačkih identiteta sa kanonskim proizvodima;
- candidate workflow za nepoznate proizvode;
- odobreno kreiranje ili povezivanje Canonical Product zapisa.

Ne sme da menja istorijske Supplier Snapshot ili Delta rezultate.

### Catalog

Catalog je postojeći vlasnik kanonskih Product i Category podataka.

Supplier Platform:

- ne importuje Catalog repository;
- ne duplira Product model;
- ne upisuje direktno u Catalog;
- prosleđuje promene samo kroz buduću odobrenu integracionu granicu.

## Dashboard

Dashboard daje poslovni pregled, ali nije izvršni pipeline niti novi izvor
istine. On agregira postojeće persisted činjenice.

Za svakog dobavljača prikazuje četiri osnovne faze:

1. **Konekcija** — dolazi iz Connection statusa, poslednjeg Probe rezultata i
   trenutne dostupnosti kredencijala.
2. **Schema** — pokazuje da li postoji aktivan Schema Profile za izabrani
   Connection.
3. **Mapping** — pokazuje da li postoji aktivan Mapping Profile za aktivnu
   Schema verziju.
4. **Acquisition** — pokazuje rezultat poslednjeg run-a, vreme poslednjeg
   uspeha i broj prihvaćenih zapisa.

Dashboard može prikazati upozorenja za neuspelu obradu, zastareo cenovnik ili
neuobičajen pad broja zapisa. Snapshot, Delta i Incident podaci mogu se
prikazati u detaljima, ali ne zamenjuju osnovne četiri faze.

## Secrets

### Development provider

Development provider čuva stvarne vrednosti samo u memoriji API procesa i
vraća neprozirnu `secret:runtime/...` referencu. Restart ili zamena API
kontejnera briše vrednosti. Referenca ostaje u bazi radi stanja konfiguracije,
ali API tada vraća `credentials_available=false`, Probe i Acquisition završavaju
bezbednom poslovnom porukom, a UI traži ponovni unos.

Ovo ponašanje je namerno, fail-closed i nije produkcioni storage.

### Production provider

Trenutni production provider je fail-closed granica. Odbija čuvanje i
rezoluciju dok se ne odobri i konfiguriše spoljašnji Secret Provider.

### Zašto tajne nisu u `configuration` JSON-u

- Configuration se vraća kroz javni API i koristi u administrativnom UI-u.
- Configuration se verzioniše, poredi i može ući u audit događaje.
- URL i query konfiguracija mogu završiti u logovima ili dijagnostici.
- Odvojena referenca omogućava zamenu produkcionog vault-a bez promene modela
  Connection-a.

Zato lozinke, tokeni i API ključevi nikada ne smeju biti deo URL-a,
`request_headers`, `query_parameters` ili drugog javnog configuration polja.

## Zašto baza nije menjana

Za stabilizaciju Pipeline-a nisu bile potrebne nove tabele, kolone ili
migracije:

- Connection već poseduje `secret_reference` i poslednji validation status;
- Acquisition, Schema, Mapping, Snapshot i Delta već imaju svoje persisted
  modele;
- Probe je kratkotrajna verifikaciona operacija, ne novi poslovni agregat;
- Dashboard je read-only agregacija postojećih činjenica;
- dostupnost development tajne je runtime stanje, ne trajna baza-istina.

Postojeća arhitektura je proširena servisima, adapterima, DTO-ovima i UI
agregacijom. Nije uveden paralelni pipeline niti duplicirano skladište.

## Posledice odluke

Pozitivno:

- jasne granice odgovornosti;
- Probe je bezbedan i jeftin;
- neuspešan import ne menja poslednje validno stanje;
- tajne ne ulaze u javnu konfiguraciju;
- downstream moduli dobijaju samo validne promene.

Ograničenja:

- development kredencijali nestaju posle restarta;
- FTP, SFTP, Email i Google Drive još nemaju izvršne adaptere;
- produkcija zahteva odobren spoljašnji Secret Provider;
- Supplier Platform ne završava matching sa Catalog proizvodima.

## Budući razvoj — nije deo v1.0

Sledeće komponente su planirane ekstenzije i nisu deo trenutne stabilne
implementacije:

- Production Secret Provider;
- FTP/SFTP adapteri;
- Email adapter;
- Google Drive adapter;
- Browser Automation, samo ako ikada bude posebno bezbednosno i arhitektonski
  odobren.

Svaka ekstenzija mora zadržati postojeće granice: adapter pribavlja sadržaj,
Schema proverava strukturu, Mapping prevodi polja, Acquisition orkestrira
stvarni import, Snapshot čuva validno stanje, a Delta objavljuje promene.

## Stabilnost

Supplier Pipeline v1.0 smatra se stabilnom osnovom. Promena ponašanja dozvoljena
je samo za potvrđen defect, backward-compatible ekstenziju ili posebno odobrenu
cross-module integraciju. Ovaj ADR ne odobrava razvoj Canonical Products,
Pricing, ERP ili drugih narednih poslovnih modula.
