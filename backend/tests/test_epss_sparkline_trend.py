"""Sanity checks for EPSS trend thresholds (mirrors frontend epssTrendLabel)."""

from datetime import date, timedelta


def _trend_label(history, current_score):
    """Python mirror of frontend absolute-delta trend logic."""
    from datetime import datetime

    points = list(history)
    today_s = date.today().isoformat()
    if current_score is not None:
        if points and points[-1][0] == today_s:
            points[-1] = (today_s, current_score)
        else:
            points.append((today_s, current_score))
    points.sort(key=lambda x: x[0])
    if len(points) < 2:
        return "Stable"

    latest_date, latest_score = points[-1]
    target_ms = datetime.fromisoformat(f"{latest_date}T12:00:00").timestamp() - 7 * 86400
    baseline = points[0]
    best = abs(datetime.fromisoformat(f"{baseline[0]}T12:00:00").timestamp() - target_ms)
    for p in points:
        d = abs(datetime.fromisoformat(f"{p[0]}T12:00:00").timestamp() - target_ms)
        if d < best:
            best = d
            baseline = p

    change = latest_score - baseline[1]
    if change > 0.05:
        return "Rising"
    if change < -0.05:
        return "Falling"
    return "Stable"


def test_rising_when_absolute_change_above_threshold():
    today = date.today()
    history = [
        ((today - timedelta(days=14)).isoformat(), 0.30),
        ((today - timedelta(days=7)).isoformat(), 0.40),
    ]
    assert _trend_label(history, 0.91) == "Rising"


def test_falling_when_absolute_change_below_threshold():
    today = date.today()
    history = [
        ((today - timedelta(days=14)).isoformat(), 0.90),
        ((today - timedelta(days=7)).isoformat(), 0.80),
    ]
    assert _trend_label(history, 0.70) == "Falling"


def test_stable_when_change_within_band():
    today = date.today()
    history = [
        ((today - timedelta(days=14)).isoformat(), 0.50),
        ((today - timedelta(days=7)).isoformat(), 0.52),
    ]
    assert _trend_label(history, 0.53) == "Stable"
