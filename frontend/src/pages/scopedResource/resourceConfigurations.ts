import type { ResourceConfiguration } from "./resourceModel";

export const resourceConfigurations: Record<string, ResourceConfiguration> = {
  schemas: {
    resource: "schema-profiles",
    title: "Schema Profiles",
    description: "Verzije očekivane strukture, aktivacija, polja i validacija.",
    codeField: "schema_code",
    permissionRead: "schema_profiles.read",
    permissionWrite: "schema_profiles.write",
    extraColumns: [
      { key: "version_number", label: "Verzija", tooltip: "Nepromjenljiva poslovna verzija schema profila." },
      { key: "field_count", label: "Polja", tooltip: "Broj detektovanih aktivnih Schema Fields." }
    ],
    actions: [
      { name: "reanalyze", label: "Ponovo analiziraj izvor", tooltip: "Ponovo preuzima izvor i zamenjuje polja ove DRAFT verzije.", permission: "schema_profiles.write", icon: "retry" },
      { name: "activate", label: "Aktiviraj", tooltip: "Aktivira ovu verziju kroz backend lifecycle.", permission: "schema_profiles.activate", icon: "play" },
      { name: "archive", label: "Arhiviraj", tooltip: "Arhivira profil bez brisanja istorije.", permission: "schema_profiles.activate", icon: "cancel" }
    ]
  },
  acquisitions: {
    resource: "acquisitions",
    title: "Acquisition Runs",
    description: "Ručno izvršavanje, upload, retry/cancel, greške, statistika i timeline.",
    codeField: "acquisition_code",
    permissionRead: "acquisitions.read",
    extraColumns: [
      { key: "trigger_type", label: "Trigger", tooltip: "Način pokretanja Acquisition Run-a." },
      { key: "total_record_count", label: "Zapisi", tooltip: "Ukupan broj pročitanih source redova." },
      { key: "failure_message", label: "Razlog neuspeha", tooltip: "Bezbedna poslovna poruka koju je sačuvao backend." }
    ],
    actions: [
      { name: "retry", label: "Ponovi", tooltip: "Kreira novi pokušaj preko postojećeg backend servisa.", permission: "acquisitions.execute", icon: "retry" },
      { name: "cancel", label: "Otkaži", tooltip: "Otkazuje dozvoljeni aktivni Run.", permission: "acquisitions.cancel", icon: "cancel" }
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
      { key: "status", label: "Build status", tooltip: "Rezultat izgradnje Snapshot-a." },
      { key: "total_items", label: "Stavke", tooltip: "Broj Snapshot Item zapisa." }
    ],
    actions: [
      { name: "verify", label: "Proveri integritet", tooltip: "Backend ponovo proverava checksum i integritet.", permission: "snapshots.verify", icon: "play" },
      { name: "restore", label: "Vrati online", tooltip: "Pokreće postojeći restore ugovor za arhivirani Snapshot.", permission: "snapshots.restore", icon: "retry" }
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
      { name: "retry", label: "Ponovi", tooltip: "Ponavlja neuspešno poređenje bez promene snapshot-a.", permission: "deltas.calculate", icon: "retry" },
      { name: "cancel", label: "Otkaži", tooltip: "Otkazuje aktivni Delta Run.", permission: "deltas.cancel", icon: "cancel" }
    ]
  }
};
