"""Constrained decoding on Ou et al. (DECODING.md). Runs in the MODEL environment.

    python decoding/run_constrained.py --regime trio --shard 0 --nshards 8

Identical to headroom/run_models.py's ou_band run (same weights, prompt, sampling
kwargs, history rule, and the SAME per-movement seed, so the two arms are paired)
except for one LogitsProcessor that masks tokens which would add a hard
violation, decided by GrowingChecker (frozen checker rules).

REMI-z grammar, mirrored exactly from remi_z.MultiTrack.from_remiz_str:
  i-N sets the instrument, o-N the position (persists across instruments),
  p-N the pitch (N >= 128 means N - 128), d-N creates the note (inst, pos,
  pitch, duration) if pos and pitch are set, then clears the pitch.
Masks: pitch tokens whose note (at the current instrument and position) would
violate; duration tokens, only when the note could overlap notes committed
later in time in the same part, or the position changed after the pitch.
Off-ensemble instruments are not masked (the harness drops them).

Output: headroom/data/out/<ou_band|ou_piano>_masked/<regime>/<idx>.json, same format as the
unconstrained run, plus masking diagnostics.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import zlib
from fractions import Fraction
from pathlib import Path

import torch
from transformers import LogitsProcessor, LogitsProcessorList

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "headroom"))
from run_models import M2M, REGIME_PROGRAMS, SRC, source_midi  # noqa: E402

sys.path.insert(0, str(M2M))
from arrangement.decode.growing import GrowingChecker  # noqa: E402
from arrangement.instruments import load_ensemble  # noqa: E402

OUT = ROOT / "headroom" / "data" / "out"
PROGRAM_PART = {"trio": {40: 0, 41: 1, 42: 2}, "duo": {40: 0, 42: 1}, "solo_violin": {40: 0},
                "solo_flute": {73: 0}, "piano": {0: 0}}
# unconstrained system each regime is paired with (headroom/measure.py PRIMARY)
BASE_SYSTEM = {r: ("ou_piano" if r == "piano" else "ou_band") for r in PROGRAM_PART}
POS_PER_Q = 12
MAX_DUR_POS = 127


class Tokens:
    def __init__(self, tk):
        v = tk.get_vocab()
        self.id2tok = {i: t for t, i in v.items()}
        self.pitch_ids: dict[int, list[int]] = {}
        self.dur_ids: dict[int, int] = {}
        for t, i in v.items():
            if t.startswith("p-") and t[2:].isdigit():
                self.pitch_ids.setdefault(int(t[2:]) % 128, []).append(i)
            elif t.startswith("d-") and t[2:].isdigit():
                self.dur_ids[int(t[2:])] = i


class Masker(LogitsProcessor):
    """Per-bar state over the generated tokens; masks pitch/duration tokens."""

    def __init__(self, toks: Tokens, checker: GrowingChecker, ens, prog_part: dict, base_ticks: int,
                 tpq: int, prompt_len: int, stats: dict):
        self.t, self.ck, self.ens, self.pp = toks, checker, ens, prog_part
        self.base, self.tpq, self.prompt_len, self.stats = base_ticks, tpq, prompt_len, stats
        self.seen = 0
        self.inst = self.pos = self.pitch = self.pitch_pos = None
        self.pitch_cache_key = None
        self.pitch_block: list[int] = []
        self.committed: list[tuple] = []   # (inst, onset_ticks, dur_ticks, pitch)

    def _onset(self, pos):
        return self.base + pos * self.tpq // POS_PER_Q

    def _feed(self, tok: str):
        if tok.startswith("i-") and tok[2:].isdigit():
            self.inst = int(tok[2:])
        elif tok.startswith("o-") and tok[2:].isdigit():
            self.pos = int(tok[2:])
        elif tok.startswith("p-") and tok[2:].isdigit():
            self.pitch = int(tok[2:]) % 128
            self.pitch_pos = self.pos
        elif tok.startswith("d-") and tok[2:].isdigit():
            if self.pos is not None and self.pitch is not None:
                inst = 0 if self.inst is None else self.inst
                dur = max(1, min(MAX_DUR_POS, int(tok[2:])))
                on = self._onset(self.pos)
                d = dur * self.tpq // POS_PER_Q
                part = self.pp.get(inst)
                if part is not None:
                    _, added = self.ck.add(on, on + d, self.pitch, part)
                    self.stats["committed"] += 1
                    self.stats["violations_committed"] += len(added)
                self.committed.append((inst, on, d, self.pitch))
            self.pitch = None

    def __call__(self, input_ids, scores):
        gen = input_ids[0, self.prompt_len:].tolist()
        for i in gen[self.seen:]:
            self._feed(self.t.id2tok.get(i, ""))
        self.seen = len(gen)
        inst = 0 if self.inst is None else self.inst
        part = self.pp.get(inst)
        if part is None or self.pos is None:
            return scores
        on = self._onset(self.pos)
        # pitch mask: recomputed only when (part, onset, number of committed notes) changes
        key = (part, on, self.ck.n)
        if key != self.pitch_cache_key:
            lo, hi = self.ens.instruments[part].low, self.ens.instruments[part].high
            block = []
            for x, ids in self.t.pitch_ids.items():
                if x < lo or x > hi or self.ck.would_add(on, on + 1, x, part):
                    block += ids
            self.pitch_block, self.pitch_cache_key = block, key
            self.stats["pitch_mask_calls"] += 1
        if self.pitch_block:
            scores[0, self.pitch_block] = -math.inf
            self.stats["pitch_steps_masked"] += 1
        # duration mask: only when the duration itself can matter
        if self.pitch is not None:
            later = any(o > on for o, _ in self.ck._all_on[part])
            # checker-v2 bow rule depends on the note's own duration
            if later or self.pitch_pos != self.pos or self.ens.instruments[part].strings is not None:
                block = [i for dv, i in self.t.dur_ids.items()
                         if self.ck.would_add(on, on + max(1, min(MAX_DUR_POS, dv)) * self.tpq // POS_PER_Q,
                                              self.pitch, part)]
                if block:
                    scores[0, block] = -math.inf
                    self.stats["dur_steps_masked"] += 1
        if torch.isinf(scores).all():
            self.stats["all_masked"] += 1
        return scores


def run(rec: dict, regime: str, tmp: Path, model, toks: Tokens) -> dict:
    from remi_z import Bar, MultiTrack
    diag = source_midi(rec, tmp)
    mt = MultiTrack.from_midi(str(tmp))
    bars = [(Fraction(a), Fraction(b)) for a, b in rec["bars"]]
    starts = [a for a, _ in bars]
    tpq = math.lcm(POS_PER_Q, *[x.denominator for b in bars for x in b])
    ens = load_ensemble(regime)
    ck = GrowingChecker(ens, tpq, MAX_DUR_POS * tpq // POS_PER_Q, capacity=4096)
    stats = dict(committed=0, violations_committed=0, pitch_mask_calls=0, pitch_steps_masked=0,
                 dur_steps_masked=0, all_masked=0, bars_note_mismatch=0)
    insts = REGIME_PROGRAMS[regime]
    notes, n_trunc, n_fail, prev = [], 0, 0, None
    for i, bar in enumerate(mt):
        inp = model.assemble_model_input(bar, prev, insts)
        base = starts[i] if i < len(starts) else starts[-1] + (i - len(starts) + 1) * bars[-1][1]
        masker = Masker(toks, ck, ens, PROGRAM_PART[regime], int(base * tpq), tpq, inp.shape[1], stats)
        out = model.model.generate(inp, pad_token_id=model.tk.pad_token_id,
                                   logits_processor=LogitsProcessorList([masker]), **model.generate_kwargs)
        # feed any token the processor did not see (the last sampled token)
        for t in out[0, inp.shape[1]:].tolist()[masker.seen:]:
            masker._feed(toks.id2tok.get(t, ""))
        s = model.tk.batch_decode(out)[0]
        tail = s.split("[SEP]")[1] if "[SEP]" in s else ""
        if "[EOS]" not in tail:
            n_trunc += 1
        try:
            ob = Bar.from_remiz_str(tail.split("[EOS]")[0].strip())
        except Exception:
            n_fail += 1
            ob = None
        if ob is not None:
            parsed = []
            for inst_id, tr in ob.tracks.items():
                for n in tr.notes:
                    notes.append([int(inst_id), str(base + Fraction(n.onset, 12)), str(Fraction(n.duration, 12)),
                                  int(n.pitch)])
                    parsed.append((int(inst_id), int(n.onset), int(n.duration), int(n.pitch)))
            mine = [(c[0], (c[1] - int(base * tpq)) * POS_PER_Q // tpq, c[2] * POS_PER_Q // tpq, c[3])
                    for c in masker.committed]
            if sorted(parsed) != sorted(mine):
                stats["bars_note_mismatch"] += 1
            prev = ob
    return {"notes": notes, "n_bars_model": len(mt), "n_bars_source": len(rec["bars"]),
            "bars_truncated_at_max_length": n_trunc, "bars_unparseable": n_fail, "masking": stats, **diag}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--regime", default="trio", choices=list(PROGRAM_PART))
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", type=int, nargs="*", default=None)
    ap.add_argument("--out-name", default=None, help="output folder under headroom/data/out (default <base>_masked)")
    a = ap.parse_args(argv)
    base_sys = BASE_SYSTEM[a.regime]
    if base_sys == "ou_piano":
        from api.arranger import PianoArranger
        model = PianoArranger("LongshenOu/m2m_pianist_dur", hf_ckpt=True)
    else:
        from api.arranger import BandArranger
        model = BandArranger("LongshenOu/m2m_arranger", hf_ckpt=True)
    toks = Tokens(model.tk)
    out_dir = OUT / (a.out_name or f"{base_sys}_masked") / a.regime
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f".tmp_{a.shard}.mid"
    files = sorted(SRC.glob("*.json"))
    if a.only is not None:
        files = [f for f in files if int(f.stem) in a.only]
    files = files[a.shard::a.nshards][: a.limit]
    for f in files:
        dst = out_dir / f.name
        if dst.exists():
            continue
        rec = json.loads(f.read_text())
        seed = zlib.crc32(f"{rec['key']}|{base_sys}|{a.regime}".encode())   # same seed as unconstrained: paired
        torch.manual_seed(seed)
        t0 = time.time()
        with torch.no_grad():
            res = run(rec, a.regime, tmp, model, toks)
        res.update({"idx": rec["idx"], "key": rec["key"], "system": f"{base_sys}_masked", "regime": a.regime,
                    "seed": seed, "seconds": time.time() - t0})
        dst.write_text(json.dumps(res))
        print(f.name, f"{res['seconds']:.0f}s", len(res["notes"]), "notes", json.dumps(res["masking"]), flush=True)
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
