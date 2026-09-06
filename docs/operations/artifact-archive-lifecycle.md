# Životni ciklus originalnih cenovnika

Originalni cenovnik ostaje audit artefakt svakog importa. Novi importi sa istim
SHA-256 checksumom zadržavaju odvojene zapise i jedinstvene reference, ali na
fajl sistemu koriste hard-link kada ga skladište podržava. Ako hard-link nije
dostupan, sistem bezbedno pada nazad na zasebnu kopiju.

## Udaljena arhiva

Podržani backend `MOUNT` predstavlja SMB/CIFS ili NFS lokaciju koju operativni
sistem montira izvan aplikacije. Aplikacija ne prima NAS lozinke niti proizvoljne
apsolutne putanje. U Docker okruženju dozvoljeni koren je `/archive-targets`, a
host putanja se podešava kroz `ARTIFACT_ARCHIVE_HOST_PATH`.

Redosled je fail-closed:

1. administrator čuva relativnu putanju;
2. test konekcije proverava upis, čitanje i uklanjanje probnog fajla;
3. tek uspešno testirano i uključeno odredište prima artefakte;
4. sadržaj se upisuje atomskom zamenom u `blobs/sha256/...`;
5. veličina i SHA-256 udaljene kopije se ponovo proveravaju;
6. rezultat i broj pokušaja ostaju u `artifact_archive_transfers`.

Greška udaljene arhive ne briše lokalni fajl i ne poništava uspešan import.
Prenos ostaje označen kao neuspešan i može se ponoviti iz System stranice.

`local_retention_days` je politika za sledeću, zasebno potvrđenu fazu lokalnog
offload-a. Ova verzija namerno ne briše lokalne cenovnike: brisanje će biti
dozvoljeno tek uz dvostepeni pregled i isključivo za checksum-verifikovane
kopije bez aktivnog hold-a.
