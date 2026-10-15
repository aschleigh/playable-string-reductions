"""Instrument and ensemble definitions, loaded from YAML (arrangement/config/).

No thresholds live in code: every number the checker uses comes from an
InstrumentDef built here from the config file.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_INSTRUMENTS = CONFIG_DIR / "instruments.yaml"


@dataclass(frozen=True)
class HandSpan:
    semitones: int        # max span within one hand
    fingers: int          # max simultaneous notes per hand


@dataclass(frozen=True)
class Transition:
    max_leap_at_zero_gap: float
    semitones_per_quarter_gap: float
    time_basis: str = "release"   # "release": next onset - previous release; "onset": - previous onset

    def allowed(self, gap: float) -> float:
        return self.max_leap_at_zero_gap + self.semitones_per_quarter_gap * gap


@dataclass(frozen=True)
class StringSpec:
    """checker-v2/v3 string rules (arrangement/checker/rules_v2.py)."""
    open: tuple[int, ...]          # open-string pitches, low to high
    max_stretch: int               # stopped notes of one chord: max offset - min offset
    bow_max_sustained: int         # notes that may sound together longer than bow_sustain_max_dur
    bow_sustain_max_dur: float     # quarter notes
    shift_max_semitones: int       # hand move between consecutive notes ...
    shift_min_time: float          # ... allowed only with at least this much time (quarter notes)
    max_offset: int = 0            # = range.high - top open string (set by the loader)
    triple_max_stretch: int | None = None   # checker-v3: stretch limit when 3+ notes sound together
    triple_min_gap: float | None = None     # checker-v3: quarters between consecutive 3+-note moments
    triple_recover: float | None = None     # checker-v5: quarters from a 3+-note onset to the next onset in the part
    double_min_gap: float | None = None     # checker-v4: quarters between consecutive 2+-note moments;
                                            # also switches on double_onset and restrike


@dataclass(frozen=True)
class InstrumentDef:
    key: str
    monophonic: bool
    low: int
    high: int
    max_chord: int | None
    hand_span: HandSpan | None
    transition: Transition | None
    names: tuple[str, ...] = ()   # regexes identifying this instrument by part name
    strings: StringSpec | None = None      # checker-v2: string instruments only
    hand_leap: Transition | None = None    # checker-v2: keyboards only (time basis: onset)


@dataclass(frozen=True)
class Ensemble:
    name: str
    part_names: tuple[str, ...]
    instruments: tuple[InstrumentDef, ...]   # index = part index
    exclude_part_names: tuple[str, ...] = ()  # regexes: declared parts that are not players

    def __len__(self) -> int:
        return len(self.instruments)


def _strings(d: dict) -> StringSpec | None:
    s = d.get("strings")
    if s is None:
        return None
    op = tuple(int(x) for x in s["open"])
    return StringSpec(open=op, max_stretch=int(s["max_stretch"]), bow_max_sustained=int(s["bow_max_sustained"]),
                      bow_sustain_max_dur=float(s["bow_sustain_max_dur"]),
                      shift_max_semitones=int(s["shift"]["max_semitones"]), shift_min_time=float(s["shift"]["min_time"]),
                      max_offset=int(d["range"]["high"]) - op[-1],
                      triple_max_stretch=None if "triple" not in s else int(s["triple"]["max_stretch"]),
                      triple_min_gap=None if "triple" not in s else float(s["triple"]["min_gap"]),
                      triple_recover=None if "triple" not in s or "recover" not in s["triple"]
                      else float(s["triple"]["recover"]),
                      double_min_gap=None if "double" not in s else float(s["double"]["min_gap"]))


def _instrument(key: str, d: dict) -> InstrumentDef:
    mono = bool(d["monophonic"])
    max_chord = d.get("max_chord")
    if mono and max_chord is not None:
        raise ValueError(f"{key}: monophonic instruments must have max_chord: null")
    if not mono and max_chord is None:
        raise ValueError(f"{key}: polyphonic instruments need max_chord")
    hs = d.get("hand_span")
    tr = d.get("transition")
    inst = InstrumentDef(
        key=key, monophonic=mono, low=int(d["range"]["low"]), high=int(d["range"]["high"]),
        max_chord=None if max_chord is None else int(max_chord),
        hand_span=None if hs is None else HandSpan(int(hs["semitones"]), int(hs["fingers"])),
        transition=None if tr is None else Transition(float(tr["max_leap_at_zero_gap"]),
                                                      float(tr["semitones_per_quarter_gap"]),
                                                      str(tr.get("time_basis", "release"))),
        names=tuple(d.get("names", ())),
        strings=_strings(d),
        hand_leap=None if d.get("hand_leap") is None else Transition(
            float(d["hand_leap"]["max_leap_at_zero_gap"]), float(d["hand_leap"]["semitones_per_quarter_gap"]), "onset"),
    )
    if inst.transition is not None and inst.transition.time_basis not in ("release", "onset"):
        raise ValueError(f"{key}: transition.time_basis must be 'release' or 'onset'")
    if inst.low > inst.high:
        raise ValueError(f"{key}: range low > high")
    return inst


def load_instruments(path: str | Path = DEFAULT_INSTRUMENTS) -> dict[str, InstrumentDef]:
    raw = yaml.safe_load(Path(path).read_text())
    return {k: _instrument(k, v) for k, v in raw.items()}


def load_ensemble(path: str | Path, instruments: dict[str, InstrumentDef] | None = None) -> Ensemble:
    """`path` is a YAML file, or a bare name looked up in config/ensembles/."""
    p = Path(path)
    if not p.suffix:
        p = CONFIG_DIR / "ensembles" / f"{path}.yaml"
    raw = yaml.safe_load(p.read_text())
    instruments = instruments if instruments is not None else load_instruments()
    parts = raw["parts"]
    return Ensemble(
        name=raw["name"],
        part_names=tuple(x["name"] for x in parts),
        instruments=tuple(instruments[x["instrument"]] for x in parts),
        exclude_part_names=tuple(raw.get("exclude_part_names", ())),
    )
