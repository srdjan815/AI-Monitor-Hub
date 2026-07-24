import pytest
from pydantic import ValidationError

from app.modules.catalog.enums import AttributeScope
from app.modules.catalog.schemas import AttributeCreate, CategoryCreate
from app.modules.catalog.utils import stable_code


def test_category_name_is_preserved() -> None:
    category = CategoryCreate(name="Matične ploče")
    assert category.name == "Matične ploče"


def test_stable_code_transliterates_serbian_characters() -> None:
    assert stable_code("Matične ploče") == "maticne_ploce"
    assert (
        stable_code("ID proizvoda / Šifra proizvoda") == "id_proizvoda_sifra_proizvoda"
    )


def test_category_attribute_requires_category() -> None:
    with pytest.raises(ValidationError):
        AttributeCreate(name="Socket", scope=AttributeScope.CATEGORY)


def test_global_attribute_rejects_category() -> None:
    with pytest.raises(ValidationError):
        AttributeCreate(
            name="Boja",
            scope=AttributeScope.GLOBAL,
            category_id="4c5e475b-23df-4a95-a2e4-3efb2c576d54",
        )
