from dinner_rush_core.config import load_config


def test_loads_menu_front_of_house_and_speed_from_the_checked_in_example() -> None:
    config = load_config()

    assert config.speed in (1, 10, 60)
    assert config.front_of_house.delivery_fee_cents == 299
    assert config.front_of_house.free_delivery_threshold_cents == 4000

    skus = {item.sku for item in config.menu}
    assert "MARG" in skus
    assert "PART" in skus


def test_menu_item_carries_price_and_cook_times() -> None:
    config = load_config()
    margherita = next(item for item in config.menu if item.sku == "MARG")

    assert margherita.price_cents == 1200
    assert margherita.prep_seconds == 90
    assert margherita.bake_seconds == 420
    assert margherita.oven_slots == 1
