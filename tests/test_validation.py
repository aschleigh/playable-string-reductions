"""Step 4 tooling: triage classification rules and summary statistics."""
from arrangement.triage import classify
from arrangement.validate import summarize


def _v(check, measured, limit, feats=(), pitches=(60,)):
    return {"check": check, "measured": measured, "limit": limit, "xml_features": list(feats),
            "notes": [{"pitch": p} for p in pitches]}


def test_classify_rules():
    assert classify(_v("range", 88, 81, ["diamond_notehead"])) == "harmonic_notation"
    assert classify(_v("range", 88, 81, ["harmonic_text"])) == "harmonic_notation"
    assert classify(_v("range", 101, 100)) == "range_above_placeholder"
    assert classify(_v("range", 35, 36, ["tremolo"])) == "below_open_string"
    assert classify(_v("chord_size", 5, 4, ["multi_voice"], (55, 62, 70, 79, 79))) == "shared_unison"
    assert classify(_v("chord_size", 6, 4, ["diamond_notehead"], (63, 70, 72, 77, 82, 89))) == "harmonic_notation"
    assert classify(_v("transition", 30, 24)) == "transition_placeholder"


def test_summarize_rates_and_concentration():
    rows = [{"key": f"m{i}", "n_notes": 100, "check_ms": 1.0,
             "counts": {"floor": {"transition": 2} if i == 0 else {}, "naive": {"chord_size": 1}, "continuity": {}}}
            for i in range(20)]
    s = summarize(rows)
    assert s["floor"]["transition"]["per_100_notes"] == 0.1
    assert s["floor"]["transition"]["per_movement_rate"]["movements_with_any"] == 1
    assert s["floor"]["transition"]["share_of_violations_in_top_5pct_movements"] == 1.0
    assert s["naive"]["chord_size"]["per_100_notes"] == 1.0
    assert s["continuity"]["range"]["violations"] == 0
