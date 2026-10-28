from belvo.config import Protocol, commission_percent


def test_point_in_time_and_contract_boundaries():
    p = Protocol.load()
    assert p.known_attempt_through("2026-03-01") == "2026-02-27"
    assert p.known_attempt_through("2026-04-01") == "2026-03-30"
    assert p.a_available("2026-06-30")
    assert not p.a_available("2026-07-01")
    assert p.sample_capacity == 666666


def test_commission_boundaries():
    assert [commission_percent(x) for x in (0, 5, 6, 15, 16, 30, 31, 60, 61, 90, 91)] == [
        15,
        15,
        20,
        20,
        25,
        25,
        30,
        30,
        40,
        40,
        50,
    ]
