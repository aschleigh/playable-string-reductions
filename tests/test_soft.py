"""Known-answer tests for the provisional soft tier (arrangement/soft).
Thresholds come from tests/fixtures/soft_test.yaml (assumed_qpm 60: 1 quarter = 1 s)."""
import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest

from arrangement.eval.record import ArrangementRecord, make_score, save
from arrangement.instruments import Ensemble, InstrumentDef, load_instruments
from arrangement.soft import COST_TYPES, load_config, soft_cost

FIX = Path(__file__).parent / "fixtures" / "soft_test.yaml"
INST = load_instruments()
CLAR = InstrumentDef(key="clarinet_bb", monophonic=True, low=50, high=94, max_chord=None,
                     hand_span=None, transition=None)


def ens(*keys):
    defs = tuple(CLAR if k == "clarinet_bb" else INST[k] for k in keys)
    return Ensemble(name="t", part_names=keys, instruments=defs)


def cost(key, notes, t, config=FIX):
    s = make_score([(key, key)], [(0, o, d, x) for o, d, x in notes])
    r = soft_cost(s, ens(key), config)
    return r[f"{t}__cost"], r[f"{t}__events"]


def test_breath():
    # 0-10 continuous = 10 s phrase, 2 s over the 8 s limit; breath gap of 1, then a 2 s phrase
    notes = [(0, 4, 72), (4, 4, 74), (8, 2, 76), (11, 2, 72)]
    assert cost("flute", notes, "breath") == (2.0, 1)


def test_bow():
    assert cost("violin", [(0, 6, 69), (6, 3, 69)], "bow") == (2.0, 1)


def test_shift():
    # 62 -> 74 after 0.5 q: 12 > 7, cost 5. 74 -> 76: in frame. 76 -> 60 after 2 q: too slow to count.
    notes = [(0, "1/2", 62), ("1/2", "5/2", 74), (3, 2, 76), (5, 1, 60)]
    assert cost("violin", notes, "shift") == (5.0, 1)


def test_crossing():
    # G3 (string 0) -> E5 (string 3) after 1 q: 2 strings skipped. E5 -> A4 (string 2) after 1/4 q: fast, 1.
    notes = [(0, 1, 55), (1, "1/4", 76), ("5/4", 1, 69)]
    assert cost("violin", notes, "crossing") == (3.0, 2)


def test_register_and_per_100():
    s = make_score([("Vn", "violin")], [(0, 0, 1, 90), (0, 1, 1, 92), (0, 2, 1, 95)])
    r = soft_cost(s, ens("violin"), FIX)
    assert (r["register__cost"], r["register__events"]) == (7.0, 2)
    assert r["register__per_100"] == pytest.approx(700 / 3)
    assert r["register__per_part"][0]["per_100"] == pytest.approx(700 / 3)


def test_key_transposing_only():
    # sounding C C# E F on a Bb clarinet -> written D D# F# G: two black keys
    notes = [(0, 1, 60), (1, 1, 61), (2, 1, 64), (3, 1, 65)]
    assert cost("clarinet_bb", notes, "key") == (2.0, 2)
    s = make_score([("Fl", "flute")], [(0, o, d, x) for o, d, x in notes])
    r = soft_cost(s, ens("flute"), FIX)
    assert r["key__applies"] is False and r["key__cost"] is None


def test_repeated():
    # 72 at 0 and 1/4 (IOI 1/4 < 1/2: cost 0.5); 72 again at 3/4 (IOI 1/2, not below the limit)
    notes = [(0, "1/4", 72), ("1/4", "1/4", 72), ("1/2", "1/4", 74), ("3/4", "1/4", 72)]
    assert cost("flute", notes, "repeated") == (0.5, 1)


def test_grace_notes_ignored():
    assert cost("violin", [(0, 0, 95), (0, 1, 69)], "register") == (0.0, 0)


def test_one_threshold_changes_one_cost_type():
    notes = [(0, 6, 92), ("6", "1/4", 76), ("25/4", "1/4", 55), ("13/2", 1, 95), ("15/2", "1/4", 95)]
    s = make_score([("Vn", "violin")], [(0, o, d, x) for o, d, x in notes])
    base_cfg = load_config(FIX)
    cfg = copy.deepcopy(base_cfg)
    cfg["instruments"]["violin"]["register"]["comfortable_high"] = 80
    a, b = soft_cost(s, ens("violin"), base_cfg), soft_cost(s, ens("violin"), cfg)
    changed = {t for t in COST_TYPES if a[f"{t}__cost"] != b[f"{t}__cost"]}
    assert changed == {"register"}
    assert a["config_sha1"] != b["config_sha1"]


def test_empty_score_is_zero():
    s = make_score([("Vn", "violin"), ("Fl", "flute")], [])
    r = soft_cost(s, ens("violin", "flute"))
    for t in COST_TYPES:
        if r[f"{t}__applies"]:
            assert r[f"{t}__cost"] == 0 and r[f"{t}__events"] == 0 and r[f"{t}__per_100"] == 0


def test_no_cross_type_aggregate():
    s = make_score([("Vn", "violin")], [(0, 0, 1, 69)])
    r = soft_cost(s, ens("violin"))
    assert not any(k in r for k in ("total", "total_cost", "cost", "score"))


def test_default_config_covers_real_instruments():
    cfg = load_config()
    assert set(INST) <= set(cfg["instruments"])
    assert all(not cfg["instruments"][k].get("transposition") for k in cfg["instruments"])


def test_cli_recomputes_soft_only(tmp_path):
    from arrangement.soft.__main__ import main
    src = make_score([("Vn1", "violin")], [(0, 0, 1, 95)])
    rec = ArrangementRecord(system="t", seed=None, input_id="x", ensemble="solo_violin", source=src, output=src,
                            bars=((Fraction(0), Fraction(4)),))
    save([rec], tmp_path / "r.jsonl")
    main([str(tmp_path / "r.jsonl"), "--config", str(FIX), "--out", str(tmp_path / "o")])
    row = json.loads((tmp_path / "o" / "soft.jsonl").read_text())
    assert row["record_id"] == rec.record_id and row["soft"]["register__cost"] == 5.0
    assert (tmp_path / "o" / "soft.csv").read_text().startswith("record_id")
