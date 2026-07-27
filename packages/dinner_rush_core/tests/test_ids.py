from dinner_rush_core.ids import uuid7


def test_uuid7_sets_version_and_variant_bits() -> None:
    value = uuid7()

    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


def test_uuid7_timestamp_component_is_non_decreasing_across_calls() -> None:
    timestamps = [uuid7().int >> 80 for _ in range(50)]

    assert timestamps == sorted(timestamps)


def test_uuid7_does_not_repeat() -> None:
    values = {uuid7() for _ in range(1000)}

    assert len(values) == 1000
