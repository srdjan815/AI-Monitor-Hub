AI MONITOR HUB LAUNCHER - ISPRAVLJENA VERZIJA

1. Obrisite ili preimenujte postojeci folder:
   C:\AI-Monitor-Hub\launcher

2. Napravite novi folder:
   C:\AI-Monitor-Hub\launcher

3. Kopirajte SADRZAJ ovog foldera direktno u launcher folder.

4. Dvaput kliknite Install-Desktop-Shortcuts.ps1.
   Ako Windows blokira skriptu, otvorite PowerShell u tom folderu i pokrenite:
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-Desktop-Shortcuts.ps1

5. Za pokretanje koristite Desktop precicu "AI Monitor Hub - Pokreni".

NAPOMENA:
- Skripte su namerno napisane bez slova sa kvacicama radi kompatibilnosti sa Windows PowerShell 5.1.
- Zaustavljanje NE brise bazu niti Docker volumene.
OBAVEZNA TRAJNA KONFIGURACIJA
============================

Pre prvog pokretanja:

1. Kopirajte C:\AI-Monitor-Hub\.env.secrets.example kao .env.secrets.
2. U AI_MONITOR_ADMIN_TOKEN unesite slučajan token od najmanje 32 znaka.
3. Kopirajte config\supplier-secrets.example.json kao
   config\supplier-secrets.json.
4. Ključ svakog zapisa mora biti postojeći secret_reference Source
   Connection zapisa. Unesite credentials i odgovarajuće parameter nazive.
5. Ograničite Windows ACL tako da ova dva fajla može čitati samo nalog koji
   pokreće Docker Desktop i administratori računara.

Launcher nikada ne generiše niti prikazuje token. API i worker čitaju isti
supplier-secrets.json preko read-only Docker mount-a. Posle izmene
.env.secrets potrebno je ponovo kreirati API kontejner. Supplier credentials
se ponovo čitaju iz JSON fajla pri svakoj upotrebi.
