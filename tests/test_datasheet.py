import pytest

from pvysics.datasheet import load_generic_datasheet


def test_generic_datasheet_matches_the_250_w_module():
    datasheet = load_generic_datasheet()

    assert datasheet.ns == 60
    assert datasheet.pmpp_w == pytest.approx(250.0)
    assert datasheet.isc_a == pytest.approx(8.9)
    assert datasheet.voc_v == pytest.approx(37.8)
    assert datasheet.impp_a == pytest.approx(8.3)
    assert datasheet.vmpp_v == pytest.approx(30.1)
    assert datasheet.ki_pct_per_c == pytest.approx(0.05)
    assert datasheet.kv_pct_per_c == pytest.approx(-0.32)
