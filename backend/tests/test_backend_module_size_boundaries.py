from __future__ import annotations

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MAX_MODULE_LINES = 350


def _bounded_modules() -> set[Path]:
    app = BACKEND_ROOT / "app"
    return {
        *app.glob("core/security*.py"),
        *app.glob("modules/inventory/*_routes.py"),
        app / "modules/inventory/pagination.py",
        app / "modules/inventory/router.py",
        *app.glob("modules/catalog/routers/attribute_*_routes.py"),
        app / "modules/catalog/routers/product_attributes.py",
        *app.glob("modules/suppliers/source_adapters/*.py"),
    }


def test_refactored_backend_modules_remain_bounded() -> None:
    modules = _bounded_modules()
    missing = sorted(
        str(path.relative_to(BACKEND_ROOT)) for path in modules if not path.is_file()
    )
    assert missing == []

    violations = {
        str(path.relative_to(BACKEND_ROOT)): len(
            path.read_text(encoding="utf-8").splitlines()
        )
        for path in sorted(modules)
        if len(path.read_text(encoding="utf-8").splitlines()) > MAX_MODULE_LINES
    }
    assert violations == {}


def test_compatibility_facades_stay_thin() -> None:
    facades = (
        BACKEND_ROOT / "app/core/security.py",
        BACKEND_ROOT / "app/modules/inventory/router.py",
        BACKEND_ROOT / "app/modules/catalog/routers/product_attributes.py",
        BACKEND_ROOT / "app/modules/suppliers/source_adapters/implementation.py",
    )
    sizes = {
        str(path.relative_to(BACKEND_ROOT)): len(
            path.read_text(encoding="utf-8").splitlines()
        )
        for path in facades
    }
    assert all(size <= 75 for size in sizes.values()), sizes
