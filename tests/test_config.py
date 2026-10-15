"""Config hygiene: every numeric threshold carries a source or a placeholder
code, and every placeholder code is listed in UNSOURCED.md."""
import re
from pathlib import Path

from arrangement.instruments import DEFAULT_INSTRUMENTS, load_ensemble, load_instruments

ROOT = Path(__file__).resolve().parent.parent
NUM_LINE = re.compile(r"^\s*[a-z_]+:\s*-?\d")


def test_every_number_has_source_or_placeholder():
    bad = []
    for ln, line in enumerate(DEFAULT_INSTRUMENTS.read_text().splitlines(), 1):
        if line.lstrip().startswith("#") or not NUM_LINE.match(line):
            continue
        comment = line.split("#", 1)[1] if "#" in line else ""
        if not (re.search(r"\[[A-Za-z]+\]", comment) or re.search(r"(PLACEHOLDER|CORPUS-CALIBRATED) \(U\d+\)", comment)):
            bad.append((ln, line))
    assert not bad, bad


def test_placeholders_listed_in_unsourced():
    codes = set(re.findall(r"(?:PLACEHOLDER|CORPUS-CALIBRATED) \((U\d+)\)", DEFAULT_INSTRUMENTS.read_text()))
    listed = set(re.findall(r"^\| (U\d+) \|", (ROOT / "UNSOURCED.md").read_text(), re.M))
    assert codes and codes <= listed


def test_quartet_loads():
    ens = load_ensemble("quartet")
    assert [i.key for i in ens.instruments] == ["violin", "violin", "viola", "cello"]
    assert not any(i.monophonic for i in ens.instruments)
    lows = {i.key: i.low for i in load_instruments().values()}
    assert {k: lows[k] for k in ("violin", "viola", "cello")} == {"violin": 55, "viola": 48, "cello": 36}


def test_headroom_regimes_load():
    expect = {"trio": ["violin", "viola", "cello"], "duo": ["violin", "cello"], "solo_violin": ["violin"],
              "solo_flute": ["flute"], "piano": ["piano"]}
    for name, keys in expect.items():
        assert [i.key for i in load_ensemble(name).instruments] == keys
    assert load_ensemble("solo_flute").instruments[0].monophonic
    assert load_ensemble("piano").instruments[0].hand_span is not None
