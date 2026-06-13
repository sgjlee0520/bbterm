from bbterm.data.providers.base import CostCapExceeded


def test_cost_cap_exceeded_carries_amounts():
    err = CostCapExceeded(estimated_usd=2.5, cap_usd=1.0)
    assert err.estimated_usd == 2.5
    assert err.cap_usd == 1.0
    assert "2.5" in str(err) and "1.00" in str(err)
