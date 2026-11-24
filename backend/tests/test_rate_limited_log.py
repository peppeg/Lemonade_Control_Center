import logging

from app.services.rate_limited_log import RateLimitedWarning


def test_a_recurring_warning_is_logged_once_per_interval_with_a_count(caplog):
    now = [0.0]
    warning = RateLimitedWarning(logging.getLogger("test.rate"), 600, clock=lambda: now[0])

    with caplog.at_level("WARNING", logger="test.rate"):
        assert warning.warn("bad record %s", 1)
        assert not warning.warn("bad record %s", 2)
        assert not warning.warn("bad record %s", 3)
        now[0] = 601.0
        assert warning.warn("bad record %s", 4)

    assert [record.getMessage() for record in caplog.records] == [
        "bad record 1",
        "bad record 4 (and 2 more like it since the last warning)",
    ]
