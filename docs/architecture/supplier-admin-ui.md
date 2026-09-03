# Supplier Admin UI — Chapter 3.10

## Svrha

Supplier Admin UI je odvojena React aplikacija koja koristi isključivo
zamrznuti `/api/v1` REST ugovor. Backend ostaje jedini izvor lifecycle-a,
validacije, izračunavanja, dozvola i transakcija. UI nema direktan pristup
bazi i ne kreira poslovne odluke.

## Tehnologija i licence

- React 18 i TypeScript strict
- Vite
- Material UI Community i MIT icon paket
- React Router
- TanStack Query
- react-hot-toast
- date-fns

Sve zavisnosti su besplatne i open-source. Nema MUI X Pro, AG Grid
Enterprise, komercijalnog template-a, theme-a ili icon pack-a. Tačne verzije
i integritet nalaze se u `frontend/package-lock.json`.

## Struktura

```text
frontend/
  src/
    api/          centralni fetch client i typed Supplier API adapter
    components/   shell, enterprise tabela, drawer, status, async stanja
    pages/        dashboard i poslovni radni prostori
    state/        auth, theme/layout i izabrani Supplier/Source
    App.tsx       lazy routing
    theme.ts      zajednički Material UI design tokeni
```

Page komponente ne parsiraju source fajlove i ne izračunavaju Snapshot,
Delta ili Incident odluke. `supplierApi` je jedina REST granica.

## Routing

- `/dashboard`
- `/suppliers`
- `/sources`
- `/schemas`
- `/mappings`
- `/acquisitions`
- `/snapshots`
- `/deltas`
- `/incidents`
- `/archive`
- `/administration`

Sve poslovne stranice se lazy-load-uju. Nepoznata ruta se bezbedno vraća na
Dashboard.

## Layout i komponentni standard

Desktop koristi trajnu sklopivu levu navigaciju, top toolbar, breadcrumbs,
globalnu pretragu, notification ulaz i korisnički meni. Tablet koristi isti
radni prostor sa privremenom navigacijom; mobilni layout slaže filtere i
akcije vertikalno.

Zajedničke komponente:

- `EntityTable`: server pagination, allowlisted server sort/filter, sticky
  header, resize, izbor kolona, gustina, trajni layout, multi-select i CSV
  samo za već učitanu stranicu;
- `DetailDrawer`: heavy detail podatke učitava tek po otvaranju;
- `StatusChip`: uvek icon + tekst + boja;
- `MetricCard`, `WorkspaceSelector`, `GlobalSearch`, `RecordDetails`;
- `LoadingBlock`, `ErrorBlock`, `EmptyState`.

Svako novo polje i akcija mora imati srpski label, helper ili tooltip.
Modali su rezervisani za kratke create/edit forme; operativni detalji ostaju
u desnom drawer-u.

## API i server state

TanStack Query čuva server state, deduplikuje request-e i koristi kontrolisan
stale interval. Lokalni React state služi filterima, selekciji i otvorenom
drawer-u. Globalni state je ograničen na:

- Bearer token i dekodirane permission claim-ove;
- light/dark/system temu;
- navigation/density/column preference;
- izabrani Supplier i Source radni prostor.

Bearer token izdaje Foundation. UI ga ne potpisuje i čuva ga samo u
`sessionStorage`. Permission claim služi isključivo za skrivanje akcija;
backend ponovo autorizuje svaki request.

Svaki request dobija bezbedan `X-Correlation-ID`; canonical error envelope
se prikazuje bez stack trace-a, uz request ID za podršku.

## Performance

- route-level code splitting;
- bounded server pagination;
- detail query tek po otvaranju;
- nema preload-a Snapshot Item-a, Delta Item-a, Incident Event-a ili archive
  manifest-a;
- search debounce 250 ms i maksimalno 15 rezultata u toolbar-u;
- widget greške su izolovane;
- produkcijski asset-i imaju immutable cache, dok SPA fallback ostaje
  aktivan.

## Accessibility

Vidljiv `:focus-visible`, semantičke tabele, labelovani input-i, ARIA
navigation/search/button nazivi, tastaturni Enter za otvaranje reda, dovoljan
kontrast i status koji nikada ne zavisi samo od boje. Global search koristi
`Ctrl/Cmd+K`.

## Teme

Light, Dark i System preference se čuvaju u `localStorage`. System prati
`prefers-color-scheme`. Design tokeni i komponentni override-i postoje samo
u `theme.ts`.

## Razvoj

Preduslov je Node 20+:

```powershell
cd frontend
npm ci
npm run dev
```

Vite na `http://localhost:5173` prosleđuje `/api` na lokalni backend port
8000. Quality gate:

```powershell
npm run typecheck
npm run lint
npm run build
```

Produkcijski multi-stage `Dockerfile` generiše statički build i služi ga kroz
open-source nginx. `nginx.conf` očekuje Compose DNS naziv `api`; dodavanje
deployment servisa ostaje eksplicitna release/deployment odluka i nije
menjalo zamrznuti Foundation Compose.

## Proširenje

Nova stranica koristi postojeći `supplierApi`, `PageHeader`, `EntityTable` i
`DetailDrawer`. Ne uvodi drugi fetch client, paralelni RBAC, poslovni reducer
ili frontend lifecycle. Ako endpoint ne postoji, UI ne simulira ponašanje
nego traži odobren backward-compatible backend extension u kasnijem
izdanju.
