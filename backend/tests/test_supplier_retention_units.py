from app.modules.suppliers.retention_service import preview_blockers


def test_preview_blockers_reports_every_failed_safety_gate() -> None:
    blockers = preview_blockers(
        policy_enabled=False,
        protected_snapshots=1,
        snapshots_requiring_archive=2,
        candidate_snapshot_items=10,
        observations_preserved=9,
    )

    assert len(blockers) == 5
    assert "Politika nije uključena" in blockers
    assert "Postoje snapshotovi zaštićeni oznakom zadržavanja" in blockers
    assert "Snapshotovi prvo moraju imati verifikovanu arhivu" in blockers
    assert "Nisu sačuvana sva statistička opažanja" in blockers


def test_preview_blockers_keeps_only_durable_storage_gate_when_data_is_safe() -> None:
    blockers = preview_blockers(
        policy_enabled=True,
        protected_snapshots=0,
        snapshots_requiring_archive=0,
        candidate_snapshot_items=10,
        observations_preserved=10,
    )

    assert blockers == [
        "Automatsko izvršenje nije aktivirano dok snapshot arhiva nije vezana za trajno odredište"
    ]
