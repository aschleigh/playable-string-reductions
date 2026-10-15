"""Generate arrangements with the neural systems. Runs in the MODEL environment
(headroom/env.md), never the checker environment.

    python headroom/run_models.py --system ou_band --regime trio --shard 0 --nshards 8

Systems (DECISION.md amendment A1):
  ou_band   Ou et al. (NeurIPS 2025), LongshenOu/m2m_arranger, released weights.
            Per-bar generation exactly as the released api/arranger.py
            (same prompt, same sampling kwargs), except that the history slot
            holds the previous OUTPUT bar, as in the paper's own inference
            script (m2m/reinst.py, hist_autoregressive: True). The released
            api never updates prev_bar, so its history is always empty.
  ou_piano  Ou et al., LongshenOu/m2m_pianist_dur (piano reduction), same driver.
  amt       Anticipatory Music Transformer, stanford-crfm/music-medium-800k,
            accompaniment mode (SECONDARY, generation not arrangement): the
            source's Violin 1 is the control; the prompt is the first 2 bars
            of the source mapped to the trio; the model generates up to the
            end of bar 32.

Input: headroom/data/sources/<idx>.json (headroom/sources.py). The source is
written as MIDI at 120 qpm with one time signature per bar (exact bar
lengths), programs Vn1 40, Vn2 40, Va 41, Vc 42.
Output: headroom/data/out/<system>/<regime>/<idx>.json with notes as
[program, onset, duration, pitch] (exact quarter-note fractions on the
source's bar timeline) and generation diagnostics.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from fractions import Fraction
from pathlib import Path

import pretty_midi
import torch

HEAD = Path(__file__).resolve().parent
M2M = Path("/scratch/ashleyz/headroom_models/music2music_code")
sys.path.insert(0, str(M2M))

SRC = HEAD / "data" / "sources"
OUT = HEAD / "data" / "out"
SOURCE_PROGRAMS = [40, 40, 41, 42]            # Vn1, Vn2, Va, Vc
QPM = 120.0
SEC_PER_Q = 60.0 / QPM
REGIME_PROGRAMS = {"trio": [40, 41, 42], "duo": [40, 42], "solo_violin": [40], "solo_flute": [73], "piano": [0]}
AMT_BARS = 32
AMT_PROMPT_BARS = 2


def F(x: str) -> Fraction:
    return Fraction(x)


def _ts(length: Fraction) -> tuple[int, int] | None:
    """Time signature whose bar length (in quarters) is exactly `length`."""
    for den in (4, 8, 16, 2, 1, 32):
        num = length * den / 4
        if num.denominator == 1 and 1 <= num.numerator <= 64:
            return int(num.numerator), den
    return None


def source_midi(rec: dict, path: Path, parts_programs=SOURCE_PROGRAMS, max_q: Fraction | None = None) -> dict:
    pm = pretty_midi.PrettyMIDI(initial_tempo=QPM, resolution=480)
    bad_ts = 0
    prev = None
    for a, b in rec["bars"]:
        a, b = F(a), F(b)
        if max_q is not None and a >= max_q:
            break
        ts = _ts(b)
        if ts is None:
            bad_ts += 1
            ts = (4, 4)
        if ts != prev:
            pm.time_signature_changes.append(pretty_midi.TimeSignature(ts[0], ts[1], float(a) * SEC_PER_Q))
            prev = ts
    tracks = {}
    for pid, prog in enumerate(parts_programs):
        if prog is None:
            continue
        tracks[pid] = pretty_midi.Instrument(program=prog, name=rec["parts"][pid])
    for pid, on, du, pitch in rec["notes"]:
        on, du = F(on), F(du)
        if pid not in tracks or (max_q is not None and on >= max_q):
            continue
        end = on + du if max_q is None else min(on + du, max_q)
        tracks[pid].notes.append(pretty_midi.Note(80, int(pitch), float(on) * SEC_PER_Q, float(end) * SEC_PER_Q))
    pm.instruments.extend(tracks.values())
    pm.write(str(path))
    return {"bars_without_exact_time_signature": bad_ts}


def run_ou(rec: dict, regime: str, tmp: Path, model, piano: bool) -> dict:
    from remi_z import MultiTrack
    diag = source_midi(rec, tmp)
    mt = MultiTrack.from_midi(str(tmp))
    starts = [F(a) for a, _ in rec["bars"]]
    insts = REGIME_PROGRAMS[regime]
    notes, n_trunc, n_fail = [], 0, 0
    prev = None
    for i, bar in enumerate(mt):
        inp = model.assemble_model_input(bar, prev, insts)
        out = model.model.generate(inp, pad_token_id=model.tk.pad_token_id, **model.generate_kwargs)
        s = model.tk.batch_decode(out)[0]
        tail = s.split("[SEP]")[1] if "[SEP]" in s else ""
        if "[EOS]" not in tail:
            n_trunc += 1                                  # hit max_length: bar cut off
        try:
            from remi_z import Bar
            ob = Bar.from_remiz_str(tail.split("[EOS]")[0].strip())
        except Exception:
            n_fail += 1
            ob = None
        if ob is not None:
            base = starts[i] if i < len(starts) else starts[-1] + (i - len(starts) + 1) * F(rec["bars"][-1][1])
            for inst_id, tr in ob.tracks.items():
                for n in tr.notes:
                    notes.append([int(inst_id), str(base + Fraction(n.onset, 12)), str(Fraction(n.duration, 12)),
                                  int(n.pitch)])
            prev = ob
    return {"notes": notes, "n_bars_model": len(mt), "n_bars_source": len(rec["bars"]),
            "bars_truncated_at_max_length": n_trunc, "bars_unparseable": n_fail, **diag}


def run_amt(rec: dict, tmp: Path, model) -> dict:
    from anticipation import ops
    from anticipation.convert import midi_to_events
    from anticipation.sample import generate
    from anticipation.tokenize import extract_instruments
    bars = rec["bars"]
    end_q = F(bars[min(AMT_BARS, len(bars)) - 1][0]) + F(bars[min(AMT_BARS, len(bars)) - 1][1])
    prompt_q = F(bars[min(AMT_PROMPT_BARS, len(bars) - 1)][0])
    # Source mapped to the trio: Vn1 -> violin (control line), Va -> viola, Vc -> cello; Vn2 dropped.
    source_midi(rec, tmp, parts_programs=[40, None, 41, 42], max_q=end_q)
    ev = midi_to_events(str(tmp))
    events, melody = extract_instruments(ev, [40])
    hist = ops.clip(events, 0, float(prompt_q) * SEC_PER_Q, clip_duration=False)
    gen = generate(model, float(prompt_q) * SEC_PER_Q, float(end_q) * SEC_PER_Q, inputs=hist, controls=melody, top_p=.98)
    full = ops.combine(gen, melody)
    from anticipation.config import TIME_RESOLUTION
    from anticipation.vocab import DUR_OFFSET, NOTE_OFFSET, TIME_OFFSET
    q_per_bin = Fraction(1, int(TIME_RESOLUTION * SEC_PER_Q))
    notes = []
    for t, d, n in zip(full[0::3], full[1::3], full[2::3]):
        note = n - NOTE_OFFSET
        instr, pitch = note // 128, note % 128
        notes.append([int(instr), str((t - TIME_OFFSET) * q_per_bin), str(max(d - DUR_OFFSET, 1) * q_per_bin), int(pitch)])
    n_control = len(melody) // 3
    return {"notes": notes, "end_q": str(end_q), "prompt_q": str(prompt_q), "n_control_notes": n_control,
            "control_program": 40}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, choices=["ou_band", "ou_piano", "amt"])
    ap.add_argument("--regime", required=True, choices=list(REGIME_PROGRAMS))
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    out_dir = OUT / a.system / a.regime
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f".tmp_{a.shard}.mid"
    if a.system == "amt":
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained("stanford-crfm/music-medium-800k").cuda().eval()
    elif a.system == "ou_piano":
        from api.arranger import PianoArranger
        model = PianoArranger("LongshenOu/m2m_pianist_dur", hf_ckpt=True)
    else:
        from api.arranger import BandArranger
        model = BandArranger("LongshenOu/m2m_arranger", hf_ckpt=True)
    files = sorted(SRC.glob("*.json"))[a.shard::a.nshards][: a.limit]
    for f in files:
        dst = out_dir / f.name
        if dst.exists():
            continue
        rec = json.loads(f.read_text())
        seed = zlib.crc32(f"{rec['key']}|{a.system}|{a.regime}".encode())
        torch.manual_seed(seed)
        t0 = time.time()
        with torch.no_grad():
            res = run_amt(rec, tmp, model) if a.system == "amt" else run_ou(rec, a.regime, tmp, model, a.system == "ou_piano")
        res.update({"idx": rec["idx"], "key": rec["key"], "system": a.system, "regime": a.regime, "seed": seed,
                    "seconds": time.time() - t0})
        dst.write_text(json.dumps(res))
        print(f.name, f"{res['seconds']:.0f}s", len(res["notes"]), "notes", flush=True)
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
