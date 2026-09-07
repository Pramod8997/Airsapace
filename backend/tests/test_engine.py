"""Unit tests for the pure statistical engine (TRD §15 unit list)."""
from __future__ import annotations

from datetime import date

from statistical_engine.aggregation import QuotePriceRow, base_period_prices, build_spec_prices
from statistical_engine.backtest import SeriesPoint, compute_metrics
from statistical_engine.basket import Basket, BasketError
from statistical_engine.index import compute_index_series, input_fingerprint, laspeyres_index
from statistical_engine.normalization import consumer_payable_fare, fare_components_consistent
from statistical_engine.outliers import flag_outliers
from statistical_engine.quality import assess_quality, is_valid_observation


def _basket() -> Basket:
    b = Basket(
        basket_version="B1", weight_version="W1", weight_source="test",
        base_period_start=date(2026, 7, 1), base_period_end=date(2026, 7, 5),
        weights={("DEL-BOM", 1): 0.6, ("DEL-BOM", 7): 0.4},
    )
    b.validate()
    return b


# ---------------------------------------------------------------- formula


def test_laspeyres_hand_computed():
    base = {("DEL-BOM", 1): 100.0, ("DEL-BOM", 7): 200.0}
    weights = {("DEL-BOM", 1): 0.6, ("DEL-BOM", 7): 0.4}
    # 0.6*110/100 + 0.4*180/200 = 0.66 + 0.36 = 1.02 -> 102.0
    assert laspeyres_index({("DEL-BOM", 1): 110.0, ("DEL-BOM", 7): 180.0}, base, weights) == 102.0


def test_index_equals_100_when_prices_equal_base():
    base = {("DEL-BOM", 1): 100.0, ("DEL-BOM", 7): 200.0}
    assert laspeyres_index(base, base, {("DEL-BOM", 1): 0.6, ("DEL-BOM", 7): 0.4}) == 100.0


def test_missing_spec_reweights_not_imputes():
    """A spec with no observation drops from numerator AND denominator."""
    base = {("DEL-BOM", 1): 100.0, ("DEL-BOM", 7): 200.0}
    weights = {("DEL-BOM", 1): 0.6, ("DEL-BOM", 7): 0.4}
    # only T+1 present: I = 110/100*100 = 110, not dragged by absent T+7
    assert laspeyres_index({("DEL-BOM", 1): 110.0}, base, weights) == 110.0


def test_no_prices_yields_none():
    assert laspeyres_index({}, _basket().weights, _basket().weights) is None


def test_determinism_same_input_same_output():
    base = {("DEL-BOM", 1): 100.0, ("DEL-BOM", 7): 200.0}
    weights = {("DEL-BOM", 1): 0.6, ("DEL-BOM", 7): 0.4}
    prices = {("DEL-BOM", 1): 113.0, ("DEL-BOM", 7): 187.0}
    r1 = laspeyres_index(prices, base, weights)
    r2 = laspeyres_index(prices, base, weights)
    assert r1 == r2

    spec_prices = {(date(2026, 7, 6), "DEL-BOM", 1): 113.0}
    b = _basket()
    h1 = input_fingerprint(spec_prices, base, b)
    h2 = input_fingerprint(spec_prices, base, b)
    assert h1 == h2 and len(h1) == 64


def test_series_cuts_present():
    spec_prices = {
        (date(2026, 7, 6), "DEL-BOM", 1): 110.0,
        (date(2026, 7, 6), "DEL-BOM", 7): 180.0,
    }
    base = {("DEL-BOM", 1): 100.0, ("DEL-BOM", 7): 200.0}
    b = _basket()
    points = compute_index_series(spec_prices, base, b, [date(2026, 7, 6)])
    cuts = {(p.route_id, p.lead_time) for p in points}
    assert (None, None) in cuts        # national combined
    assert (None, 1) in cuts           # national T+1
    assert ("DEL-BOM", None) in cuts   # route combined
    assert ("DEL-BOM", 1) in cuts      # route × lead


def test_basket_rejects_bad_weights():
    b = _basket()
    b.weights[("DEL-BOM", 1)] = -1.0
    try:
        b.validate()
        assert False, "negative weight must raise"
    except BasketError:
        pass


# ---------------------------------------------------------------- normalization


def test_payable_fare_arithmetic():
    assert consumer_payable_fare(4200, 756, 100) == 5056
    assert consumer_payable_fare(None, 756, 100) is None
    assert consumer_payable_fare(0, 0, 0) is None  # non-positive payable is unusable


def test_component_consistency():
    from collectors.core.models import FlightQuote
    from datetime import datetime
    from zoneinfo import ZoneInfo

    q = FlightQuote(
        source_id="s", origin="DEL", destination="BOM", departure_date=date(2026, 10, 7),
        airline="6E", advance_days=30, base_fare=4200, taxes=756, mandatory_fees=100,
        total_fare=5056, collected_at=datetime(2026, 9, 7, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )
    assert fare_components_consistent(q)
    q.total_fare = 5156
    assert not fare_components_consistent(q)


# ---------------------------------------------------------------- outliers


def test_fat_finger_flagged():
    flags = flag_outliers([100, 102, 98, 101, 1500])
    assert flags.flagged[4] is True and flags.reasons[4] == "fat_finger"


def test_robust_z_flagged():
    flags = flag_outliers([100, 101, 99, 100, 130])
    assert flags.flagged[4] is True and flags.reasons[4] == "robust_z"
    assert not any(flags.flagged[:4])


def test_small_group_never_flagged():
    flags = flag_outliers([100, 100000])
    assert not any(flags.flagged)


def test_none_values_untouched():
    flags = flag_outliers([None, 100, 101, 99, 130])
    assert flags.flagged[0] is False


# ---------------------------------------------------------------- quality


def _quote(**overrides):
    from collectors.core.models import FlightQuote
    from datetime import datetime
    from zoneinfo import ZoneInfo

    fields = dict(
        source_id="airline-6e-demo", origin="DEL", destination="BOM",
        departure_date=date(2026, 10, 7), departure_time="09:15", airline="6E",
        flight_number="6E123", cabin="economy", fare_class="Q", advance_days=30,
        base_fare=4200, taxes=756, mandatory_fees=100, total_fare=5056,
        collected_at=datetime(2026, 9, 7, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )
    fields.update(overrides)
    return FlightQuote(**fields)


def test_quality_high_for_clean_quote():
    q = _quote()
    result = assess_quality(q, source_reliability=0.99)
    assert result.score >= 0.9
    assert is_valid_observation(result, q.availability)


def test_duplicate_lowers_non_duplicate_component():
    clean = assess_quality(_quote(), is_duplicate=False)
    dup = assess_quality(_quote(), is_duplicate=True)
    assert dup.components["non_duplicate"] == 0.0
    assert dup.score < clean.score


def test_broken_total_makes_observation_invalid():
    q = _quote(total_fare=5056 + 999)
    result = assess_quality(q)
    assert result.components["consistency"] == 0.0
    assert not is_valid_observation(result, q.availability)


def test_sold_out_is_a_valid_observation():
    from collectors.core.models import Availability

    q = _quote(availability=Availability.SOLD_OUT)
    result = assess_quality(q)
    assert is_valid_observation(result, Availability.SOLD_OUT)


# ---------------------------------------------------------------- aggregation


def test_median_aggregation_excludes_non_available():
    rows = [
        QuotePriceRow(date(2026, 7, 6), "DEL-BOM", 1, 100.0, "AVAILABLE", False),
        QuotePriceRow(date(2026, 7, 6), "DEL-BOM", 1, 200.0, "AVAILABLE", False),
        QuotePriceRow(date(2026, 7, 6), "DEL-BOM", 1, 5000.0, "AVAILABLE", False),
        QuotePriceRow(date(2026, 7, 6), "DEL-BOM", 1, 999.0, "SOLD_OUT", False),   # excluded
        QuotePriceRow(date(2026, 7, 6), "DEL-BOM", 1, 999.0, "AVAILABLE", True),   # outlier excluded
    ]
    prices = build_spec_prices(rows)
    assert prices[(date(2026, 7, 6), "DEL-BOM", 1)] == 200.0


def test_base_period_mean():
    spec_prices = {
        (date(2026, 7, 1), "DEL-BOM", 1): 100.0,
        (date(2026, 7, 2), "DEL-BOM", 1): 110.0,
        (date(2026, 7, 6), "DEL-BOM", 1): 130.0,  # outside base window
    }
    base = base_period_prices(spec_prices, date(2026, 7, 1), date(2026, 7, 2))
    assert base[("DEL-BOM", 1)] == 105.0


# ---------------------------------------------------------------- backtest


def test_backtest_perfect_series():
    pts = [SeriesPoint(date(2026, 7, d), 100.0 + d) for d in range(1, 6)]
    m = compute_metrics(pts, pts)
    assert m.n_points == 5
    assert m.mae == 0.0 and m.rmse == 0.0 and m.mape == 0.0
    assert m.correlation == 1.0 and m.trend_direction_accuracy == 1.0


def test_backtest_constant_series_has_no_correlation():
    pts = [SeriesPoint(date(2026, 7, d), 100.0) for d in range(1, 5)]
    m = compute_metrics(pts, pts)
    assert m.correlation is None and m.trend_direction_accuracy is None


def test_backtest_alignment_inner_join():
    a = [SeriesPoint(date(2026, 7, 1), 100.0), SeriesPoint(date(2026, 7, 2), 110.0)]
    b = [SeriesPoint(date(2026, 7, 2), 120.0), SeriesPoint(date(2026, 7, 3), 130.0)]
    m = compute_metrics(a, b)
    assert m.n_points == 1
    assert m.mae == 10.0


def test_backtest_known_mae_rmse():
    a = [SeriesPoint(date(2026, 7, 1), 102.0), SeriesPoint(date(2026, 7, 2), 104.0)]
    b = [SeriesPoint(date(2026, 7, 1), 100.0), SeriesPoint(date(2026, 7, 2), 100.0)]
    m = compute_metrics(a, b)
    assert m.mae == 3.0
    assert m.rmse == 3.1623  # sqrt((2^2 + 4^2)/2)
    assert m.mape == 3.0  # (2+4)/2
