from app.core.filters import is_allowed
from app.integrations.off import _infer_tags
from app.schemas import DietaryPrefs, Product


def test_infer_tags_from_russian_names():
    assert "dairy" in _infer_tags("Творог 5%", {})
    assert set(_infer_tags("Свинина", {})) >= {"meat", "pork"}
    assert "gluten" in _infer_tags("Хлеб бородинский", {})
    assert "fish" in _infer_tags("Лосось слабосолёный", {})
    assert "egg" in _infer_tags("Яичница глазунья", {})
    assert _infer_tags("Тофу органический", {}) == []  # vegan-friendly → no blocking tags


def test_infer_tags_from_off_allergens():
    assert "dairy" in _infer_tags("Cheese", {"allergens_tags": ["en:milk"]})
    assert "gluten" in _infer_tags("Bread", {"allergens_tags": ["en:gluten"]})


def test_vegan_blocks_inferred_dairy():
    tvorog = Product(name="Творог", kcal_100=120, protein_100=17, fat_100=5,
                     carbs_100=3, tags=_infer_tags("Творог", {}))
    assert is_allowed(tvorog, DietaryPrefs(vegan=True)) is False


def test_halal_blocks_inferred_pork():
    svinina = Product(name="Свинина", kcal_100=240, protein_100=27, fat_100=14,
                      carbs_100=0, tags=_infer_tags("Свинина", {}))
    assert is_allowed(svinina, DietaryPrefs(halal=True)) is False
