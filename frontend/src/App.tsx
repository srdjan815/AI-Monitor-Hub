import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Box } from "@mui/material";
import { AppShell } from "./components/AppShell";
import { LoadingBlock } from "./components/AsyncState";
import { LoginPage } from "./pages/LoginPage";
import { useAuth } from "./state/AuthContext";

const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage }))
);
const SuppliersPage = lazy(() =>
  import("./pages/SuppliersPage").then((module) => ({ default: module.SuppliersPage }))
);
const SourcesPage = lazy(() =>
  import("./pages/SourcesPage").then((module) => ({ default: module.SourcesPage }))
);
const MappingProfilesPage = lazy(() =>
  import("./pages/MappingProfilesPage").then((module) => ({ default: module.MappingProfilesPage }))
);
const IncidentsPage = lazy(() =>
  import("./pages/IncidentsPage").then((module) => ({ default: module.IncidentsPage }))
);
const ArchivePage = lazy(() =>
  import("./pages/ArchivePage").then((module) => ({ default: module.ArchivePage }))
);
const AdministrationPage = lazy(() =>
  import("./pages/AdministrationPage").then((module) => ({ default: module.AdministrationPage }))
);
const ScopedResourcePage = lazy(() =>
  import("./pages/ScopedResourcePage").then((module) => ({ default: module.ScopedResourcePage }))
);

function ProtectedRoutes() {
  const auth = useAuth();
  if (!auth.authenticated) return <LoginPage />;
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/suppliers" element={<SuppliersPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route
          path="/schemas"
          element={<ScopedResourcePage config={resource("schemas")} />}
        />
        <Route path="/mappings" element={<MappingProfilesPage />} />
        <Route
          path="/acquisitions"
          element={<ScopedResourcePage config={resource("acquisitions")} />}
        />
        <Route
          path="/snapshots"
          element={<ScopedResourcePage config={resource("snapshots")} />}
        />
        <Route
          path="/deltas"
          element={<ScopedResourcePage config={resource("deltas")} />}
        />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/archive" element={<ArchivePage />} />
        <Route path="/administration" element={<AdministrationPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

function resource(key: string) {
  // Lazy module data is mirrored here only as display/routing configuration.
  const values = {
    schemas: {
      resource: "schema-profiles",
      title: "Schema Profiles",
      description: "Verzije očekivane strukture, aktivacija, polja i validacija.",
      codeField: "schema_code",
      permissionRead: "schema_profiles.read",
      permissionWrite: "schema_profiles.write",
      extraColumns: [
        { key: "version_number", label: "Verzija", tooltip: "Istorijska schema verzija." },
        { key: "field_count", label: "Polja", tooltip: "Broj aktivnih schema polja." }
      ],
      actions: [
        { name: "activate", label: "Aktiviraj", tooltip: "Aktiviraj profil.", permission: "schema_profiles.activate", icon: "play" as const },
        { name: "archive", label: "Arhiviraj", tooltip: "Arhiviraj profil.", permission: "schema_profiles.activate", icon: "cancel" as const }
      ]
    },
    acquisitions: {
      resource: "acquisitions",
      title: "Acquisition Runs",
      description: "Ručno izvršavanje, upload, retry/cancel, greške, statistika i timeline.",
      codeField: "acquisition_code",
      permissionRead: "acquisitions.read",
      extraColumns: [
        { key: "trigger_type", label: "Trigger", tooltip: "Način pokretanja." },
        { key: "total_record_count", label: "Zapisi", tooltip: "Ukupan broj source redova." }
      ],
      actions: [
        { name: "retry", label: "Ponovi", tooltip: "Ponovi terminalni Run.", permission: "acquisitions.execute", icon: "retry" as const },
        { name: "cancel", label: "Otkaži", tooltip: "Otkaži aktivni Run.", permission: "acquisitions.cancel", icon: "cancel" as const }
      ]
    },
    snapshots: {
      resource: "snapshots",
      title: "Snapshots",
      description: "Validno stanje dobavljača, integritet, items, arhiva i restore.",
      codeField: "snapshot_code",
      permissionRead: "snapshots.read",
      permissionWrite: "snapshots.create",
      statusField: "storage_state",
      extraColumns: [
        { key: "status", label: "Build status", tooltip: "Rezultat izgradnje." },
        { key: "total_items", label: "Stavke", tooltip: "Broj Snapshot Item zapisa." }
      ],
      actions: [
        { name: "verify", label: "Proveri integritet", tooltip: "Proveri checksum.", permission: "snapshots.verify", icon: "play" as const },
        { name: "restore", label: "Vrati online", tooltip: "Restore arhive.", permission: "snapshots.restore", icon: "retry" as const }
      ]
    },
    deltas: {
      resource: "deltas",
      title: "Delta Runs",
      description: "Poređenja Snapshot parova, sažetak i promene po poljima.",
      codeField: "delta_code",
      permissionRead: "deltas.read",
      permissionWrite: "deltas.calculate",
      extraColumns: [
        { key: "added_items", label: "Dodato", tooltip: "Broj dodatih stavki." },
        { key: "modified_items", label: "Izmenjeno", tooltip: "Broj izmenjenih stavki." },
        { key: "removed_items", label: "Uklonjeno", tooltip: "Broj uklonjenih stavki." }
      ],
      actions: [
        { name: "retry", label: "Ponovi", tooltip: "Ponovi poređenje.", permission: "deltas.calculate", icon: "retry" as const },
        { name: "cancel", label: "Otkaži", tooltip: "Otkaži aktivni Delta Run.", permission: "deltas.cancel", icon: "cancel" as const }
      ]
    }
  };
  return values[key as keyof typeof values];
}

export default function App() {
  return (
    <Suspense fallback={<Box p={4}><LoadingBlock rows={8} /></Box>}>
      <ProtectedRoutes />
    </Suspense>
  );
}
