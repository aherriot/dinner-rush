import datetime
from types import SimpleNamespace

from gateway.orders import pricing


def test_subtotal_sums_unit_price_times_qty() -> None:
    assert pricing.subtotal_cents([(1200, 2), (550, 1)]) == 2950


def test_delivery_fee_charged_below_threshold() -> None:
    config = SimpleNamespace(delivery_fee_cents=299, free_delivery_threshold_cents=4000)
    assert pricing.delivery_fee_cents(2000, config) == 299  # type: ignore[arg-type]


def test_delivery_fee_waived_at_or_above_threshold() -> None:
    config = SimpleNamespace(delivery_fee_cents=299, free_delivery_threshold_cents=4000)
    assert pricing.delivery_fee_cents(4000, config) == 0  # type: ignore[arg-type]
    assert pricing.delivery_fee_cents(5000, config) == 0  # type: ignore[arg-type]


def test_total_is_subtotal_plus_fee() -> None:
    assert pricing.total_cents(2000, 299) == 2299


def test_promised_at_buffer_is_divided_by_speed_at_point_of_use() -> None:
    accepted_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    assert pricing.promised_at(accepted_at, speed=1) == accepted_at + datetime.timedelta(
        seconds=900
    )
    assert pricing.promised_at(accepted_at, speed=10) == accepted_at + datetime.timedelta(
        seconds=90
    )
