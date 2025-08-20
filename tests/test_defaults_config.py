from apex.config import defaults as d


def test_defaults_values():
    assert d.QUIESCE_DEADLINE_MS == 50
    assert d.DWELL_MIN_STEPS == 2
    assert d.COOLDOWN_STEPS == 2
    assert d.EPISODE_TOKEN_BUDGET == 10_000
    assert d.QUEUE_CAP_PER_AGENT == 10_000
    assert d.MESSAGE_TTL_S == 60
    assert d.MAX_ATTEMPTS == 5
