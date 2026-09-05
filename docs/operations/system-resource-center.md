# Centar sistemskih resursa

Stranica **Sistem** daje administratoru read-only pregled procesora, RAM-a,
diska, veličine PostgreSQL baze i poznatih skladišta aplikacije. Pragovi za
upozorenje i kritično stanje podešavaju se kroz `SYSTEM_*_PERCENT` postavke.
Merenje memorije poštuje Linux cgroup limit kontejnera kada je dostupan.

## Granica bezbednog čišćenja

Generičko čišćenje je dozvoljeno samo za eksplicitnu allowlistu:

- `LOGOVI` (`SYSTEM_LOG_ROOT`);
- `PRIVREMENI_FAJLOVI` (`SYSTEM_TEMPORARY_ROOT`).

Cenovnici, snapshot arhive, slike artikala i podaci baze nisu deo ove
allowliste. Njihov budući retention mora poštovati poslovne veze i imati
zaseban lifecycle proces. Sistem ne prati simboličke linkove i odbija široke
putanje poput korena diska.

Čišćenje je dvostepeno. Prvi zahtev pravi pregled kandidata i kratkotrajnu,
potpisanu potvrdu vezanu za kategoriju, starost i tačan skup fajlova. Drugi
zahtev ponovo skenira skladište i prekida operaciju ako se skup promenio ili je
potvrda istekla. Broj fajlova po operaciji je ograničen postavkom
`SYSTEM_CLEANUP_MAX_FILES`.

## Audit i ovlašćenja

Pregled zahteva `system_resources.read`, a čišćenje
`system_resources.manage`. Obe dozvole podrazumevano imaju samo sistemski
administratori i interni servisni nalog. Svako izvršenje trajno beleži
operatora, kriterijum starosti, rezultat, broj fajlova i broj bajtova. Audit ne
sadrži sadržaj fajlova niti potpisni token.

Brisanje se ne pokreće automatski. Administrator prvo proverava prikazani broj
i veličinu kandidata, zatim eksplicitno potvrđuje operaciju. Pre produkcije
direktorijumi moraju biti zasebno montirani i ograničeni pravima korisnika pod
kojim aplikacija radi.
