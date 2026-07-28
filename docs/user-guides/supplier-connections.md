# Konekcije dobavljača

Stranica **Konekcije dobavljača** povezuje dobavljača sa načinom na koji
isporučuje cenovnik. Nova konekcija se prvo čuva kao nacrt, zatim se cenovnik
probno preuzima, a aktivacija je dostupna tek nakon uspešnog testa.

## DS Computers — direktan XML URL

1. Kreirajte ili izaberite dobavljača DS Computers.
2. Otvorite **Konekcije dobavljača** i izaberite **Poveži cenovnik**.
3. Izaberite **Direktan URL** i format **XML**.
4. Unesite samo javni export URL, bez korisničkog imena i lozinke.
5. Uključite **Potrebna je prijava**.
6. Izaberite prijavu pomoću korisničkog imena i lozinke.
7. Kao mesto prijave izaberite **Parametri adrese**.
8. Unesite nazive parametara koje je propisao dobavljač.
9. Javne parametre, poput uključivanja opisa i slika, unesite u sekciji
   **Napredna podešavanja**, po jedan u redu u formatu `naziv=vrednost`.
10. Unesite pristupne podatke i izaberite **Probno preuzmi cenovnik**.
11. Proverite format, veličinu, broj i pregled prvih zapisa.
12. Aktivirajte konekciju tek kada je test uspešan.

Pristupni podaci se ne čuvaju u javnoj Source konfiguraciji, ne prikazuju se
nakon čuvanja i ne treba ih unositi u URL ili javne parametre.

### Važno za development okruženje

Development izdanje čuva pristupne podatke samo u memoriji API procesa. Posle
restarta API kontejnera referenca ostaje u zapisu radi istorije, ali tajna više
nije dostupna. UI tada prikazuje upozorenje **Pristupni podaci više nisu
dostupni**, Dashboard ne prikazuje konekciju kao spremnu, a Probe i Acquisition
traže da se pristupni podaci ponovo unesu. Ovo ponašanje je namerno i ne treba
ga koristiti kao produkcioni secret sistem.

## EWE — ručno učitavanje Excel cenovnika

1. Na EWE portalu preuzmite aktuelni Excel cenovnik.
2. U čarobnjaku izaberite **Ručno učitavanje**.
3. Kao format izaberite **Excel**.
4. Podesite maksimalnu veličinu i opcioni šablon naziva fajla.
5. Sačuvajte konekciju kao nacrt.
6. Izaberite probni XML, CSV ili XLSX fajl i kliknite **Probno učitaj fajl**.
7. Proba prikazuje format, veličinu i do deset prvih zapisa, ali ne kreira
   Acquisition Run, Snapshot niti podatke u katalogu.
8. Stvarni fajl se kasnije učitava kroz Acquisition upload tok.

Automatsko preuzimanje sa portala koji zahteva CAPTCHA, JavaScript interakciju
ili ručno klikanje nije deo ove funkcionalnosti.

## Statusi

- **Nacrt** — podešavanja postoje, ali konekcija nije aktivirana.
- **Potrebna provera** — cenovnik još nije uspešno probno preuzet.
- **Radi** — poslednji test konekcije je uspešan.
- **Ne radi** — poslednji test nije uspeo.
- **Nije spremno** — konekcija može raditi, ali Schema, Mapping ili Acquisition
  još nisu spremni.

Dashboard odvojeno prikazuje stanje Konekcije, Schema, Mapping i Acquisition
faze, kako bi bilo jasno da li problem postoji kod dobavljača ili u internoj
obradi.
