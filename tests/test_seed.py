import pytest
from app.seed import seed
from app.services import balances


def test_seed_is_explicit_and_refuses_duplicates(engine):
    seed(engine)
    assert balances(engine, 1)["total_expenses_paise"] == 210000
    with pytest.raises(ValueError, match="empty database"):
        seed(engine)
    assert balances(engine, 1)["total_expenses_paise"] == 210000
