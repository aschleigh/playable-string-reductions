"""Piano calibration (BLOCK6.md Step 1a, R63): the hand thresholds that have no corpus behind them
(UNSOURCED.md U8 hand span, U12/U13 hand leap), measured on the piano parts of OpenScore Lieder (CC0,
raw_corpora/Lieder). Calibration only: nothing here is trained on.

    python -m arrangement.calibrate_piano measure [--workers 16]    -> results/calibration_piano/measure/*.json
    python -m arrangement.calibrate_piano fit                         -> results/calibration_piano/piano.json

Per piano part, at every onset t:
  sounding set  notes with onset <= t < end (what the checker's hand_span / hand_leap rules see);
  struck set    notes with onset == t (what the hands must reach at that instant).
For each: the smallest two-hand span (arrangement.checker.incremental.best_two_hand_span, 5 fingers per hand).
Between consecutive onsets: the smallest hand movement (rules_v2.hand_move) and the gap in quarters, for the
sounding and the struck sets, at a fixed generous span (24) so the move is defined.
Fit (dev = crc32 % 10 == 0 of the file path, as the string calibration): span = the dev maximum and
percentiles; leap = the string transition method (smallest a for each b on a grid, b minimising the mean
allowed leap), then the held-out floor: the share of non-dev onsets that would fail each value.
"""
from __future__ import annotations

import argparse
import json
import re
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LIEDER = ROOT / "raw_corpora" / "Lieder" / "scores"
OUT = ROOT / "results" / "calibration_piano"
PIANO = re.compile(r"\bpiano(forte)?\b|\bpf\b|\bpno\b|\bklavier\b|\bpianoforte\b", re.I)
SPAN_FOR_MOVE = 24   # overridden by --span-for-move; checker-v6 refit uses 16 (R65)
B_GRID = [0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0]


def is_dev(path: str) -> bool:
    return zlib.crc32(path.encode()) % 10 == 0


def measure_file(path: str) -> dict | None:
    import warnings
    warnings.filterwarnings("ignore")
    from arrangement.checker.incremental import best_two_hand_span
    from arrangement.checker.rules_v2 import hand_move
    from arrangement.parse import parse_score
    path, span_move, sub = path if isinstance(path, tuple) else (path, SPAN_FOR_MOVE, "measure")
    rel = str(Path(path).relative_to(LIEDER))
    out_f = OUT / sub / (re.sub(r"[^A-Za-z0-9]+", "_", rel)[-180:] + ".json")
    if out_f.exists():
        return json.loads(out_f.read_text())
    try:
        piece = parse_score(path, expand_repeats=False)
    except Exception as e:      # noqa: BLE001  (malformed files are skipped and counted)
        res = {"file": rel, "status": f"parse_error: {type(e).__name__}"}
        out_f.write_text(json.dumps(res))
        return res
    pianos = [p.part_id for p in piece.parts if PIANO.search(f"{p.name} {p.instrument_name or ''}")]
    if len(pianos) != 1:
        res = {"file": rel, "status": f"piano_parts={len(pianos)}"}
        out_f.write_text(json.dumps(res))
        return res
    ev = sorted((float(e.onset), float(e.onset + e.duration), int(e.pitch)) for e in piece.events
                if e.part_id == pianos[0] and not e.is_grace and e.duration > 0)
    onsets = sorted({o for o, _, _ in ev})
    spans_s, spans_k, moves_s, moves_k, sizes = [], [], [], [], []
    prev_s = prev_k = prev_t = None
    k = 0
    active = []
    for t in onsets:
        while k < len(ev) and ev[k][0] <= t:
            active.append(ev[k]); k += 1
        active = [n for n in active if n[1] > t]
        S = tuple(sorted({x for _, _, x in active}))
        K = tuple(sorted({x for o, _, x in active if o == t}))
        sizes.append(len(S))
        bs = best_two_hand_span(list(S), 5) if 2 <= len(S) <= 10 else None
        bk = best_two_hand_span(list(K), 5) if 2 <= len(K) <= 10 else None
        spans_s.append(-2 if len(S) < 2 or len(S) > 10 else (-1 if bs is None else bs))   # -2: not a 2-10 note set
        spans_k.append(-2 if len(K) < 2 or len(K) > 10 else (-1 if bk is None else bk))
        if prev_t is not None:
            gap = t - prev_t
            ms = hand_move(prev_s, S, 5, span_move) if prev_s and S else 0.0
            mk = hand_move(prev_k, K, 5, span_move) if prev_k and K else 0.0
            moves_s.append((ms if ms != float("inf") else -1, gap))
            moves_k.append((mk if mk != float("inf") else -1, gap))
        prev_s, prev_k, prev_t = S, K, t
    res = {"file": rel, "status": "ok", "dev": is_dev(rel), "n_notes": len(ev), "n_onsets": len(onsets),
           "span_sounding": spans_s, "span_struck": spans_k, "move_sounding": moves_s, "move_struck": moves_k,
           "max_sounding": max(sizes, default=0)}
    out_f.write_text(json.dumps(res))
    return res


def measure8_file(path: str) -> dict | None:
    """checker-v8 (R83) measurements, per piano part, using the printed staves (staff 1 = right hand, 2 = left hand):
    at every onset t, the gap (semitones) between the lowest right-hand and the highest left-hand note, for sounding sets
    (held + struck), struck sets, and struck-vs-sounding (one hand's new notes against everything the other holds or
    strikes); and per staff with a struck chord at t, its span and the time since that staff's previous onset."""
    import warnings
    warnings.filterwarnings("ignore")
    from arrangement.parse import parse_score
    rel = str(Path(path).relative_to(LIEDER))
    out_f = OUT / "measure8" / (re.sub(r"[^A-Za-z0-9]+", "_", rel)[-180:] + ".json")
    if out_f.exists():
        return json.loads(out_f.read_text())
    try:
        piece = parse_score(path, expand_repeats=False)
    except Exception as e:      # noqa: BLE001
        res = {"file": rel, "status": f"parse_error: {type(e).__name__}"}
        out_f.write_text(json.dumps(res))
        return res
    pianos = [p.part_id for p in piece.parts if PIANO.search(f"{p.name} {p.instrument_name or ''}")]
    if len(pianos) != 1:
        res = {"file": rel, "status": f"piano_parts={len(pianos)}"}
        out_f.write_text(json.dumps(res))
        return res
    ev = sorted((float(e.onset), float(e.onset + e.duration), int(e.pitch), int(e.staff_id)) for e in piece.events
                if e.part_id == pianos[0] and not e.is_grace and e.duration > 0)
    if not {s for *_, s in ev} <= {1, 2}:
        res = {"file": rel, "status": "staves_not_1_2"}
        out_f.write_text(json.dumps(res))
        return res
    gaps, chords = [], []          # gaps: (g_sounding, g_struck, g_mixed) (None if a side is empty); chords: (span, dt)
    last = {1: None, 2: None}
    active, k = [], 0
    for t in sorted({o for o, *_ in ev}):
        while k < len(ev) and ev[k][0] <= t:
            active.append(ev[k]); k += 1
        active = [n for n in active if n[1] > t]
        snd = {h: [x for _, _, x, s in active if s == h] for h in (1, 2)}
        stk = {h: [x for o, _, x, s in active if s == h and o == t] for h in (1, 2)}
        g = lambda r, l: (min(r) - max(l)) if r and l else None
        mixed = [v for v in (g(stk[1], snd[2]), g(snd[1], stk[2])) if v is not None]
        gaps.append((g(snd[1], snd[2]), g(stk[1], stk[2]), min(mixed) if mixed else None))
        for h in (1, 2):
            if stk[h]:
                if len(stk[h]) >= 2:
                    chords.append((max(stk[h]) - min(stk[h]), None if last[h] is None else t - last[h]))
                last[h] = t
    res = {"file": rel, "status": "ok", "dev": is_dev(rel), "gaps": gaps, "chords": chords}
    out_f.write_text(json.dumps(res))
    return res


def cmd_measure8(a):
    (OUT / "measure8").mkdir(parents=True, exist_ok=True)
    files = sorted(str(p) for p in LIEDER.rglob("*.mxl"))[: a.limit]
    with Pool(a.workers) as pool:
        res = pool.map(measure8_file, files, chunksize=1)
    print({k: sum(1 for r in res if r and r["status"].split(":")[0] == k) for k in {r["status"].split(":")[0] for r in res if r}})


def cmd_fit8(a):
    rows = [json.loads(p.read_text()) for p in sorted((OUT / "measure8").glob("*.json"))]
    ok = [r for r in rows if r["status"] == "ok"]
    out = {"files": len(rows), "ok": len(ok), "dev_files": sum(r["dev"] for r in ok),
           "source": "OpenScore Lieder (CC0), piano part, staff 1 = right hand, staff 2 = left hand; repeats not expanded"}
    for j, name in enumerate(("sounding", "struck", "mixed")):
        for d in (True, False):
            v = np.array([gp[j] for r in ok if r["dev"] == d for gp in r["gaps"] if gp[j] is not None])
            out[f"gap_{name}_{'dev' if d else 'heldout'}"] = {
                "n": int(len(v)), "share_below": {b: float((v < b).mean()) for b in (0, 1, 2, 3, 4)},
                "percentiles": {q: float(np.percentile(v, q)) for q in (0.1, 1, 5, 50)}}
    for d in (True, False):
        c = [(s, dt) for r in ok if r["dev"] == d for s, dt in r["chords"]]
        wide = np.array([dt for s, dt in c if 13 <= s <= 16 and dt is not None])
        narrow = np.array([dt for s, dt in c if s <= 12 and dt is not None])
        out[f"chords_{'dev' if d else 'heldout'}"] = {
            "n_chords": len(c), "share_span_gt_12": float(np.mean([s > 12 for s, _ in c])),
            "share_span_gt_16": float(np.mean([s > 16 for s, _ in c])), "n_wide_13_16": int(len(wide)),
            "wide_dt_percentiles": {q: float(np.percentile(wide, q)) for q in (0.1, 0.5, 1, 5, 10, 50)} if len(wide) else {},
            "narrow_dt_percentiles": {q: float(np.percentile(narrow, q)) for q in (0.1, 0.5, 1, 5, 10, 50)} if len(narrow) else {},
            "wide_share_dt_below": {b: float((wide < b).mean()) for b in (0.25, 0.5, 0.75, 1.0)} if len(wide) else {},
            "narrow_share_dt_below": {b: float((narrow < b).mean()) for b in (0.25, 0.5, 0.75, 1.0)} if len(narrow) else {}}
    (OUT / "piano_v8.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def fit_envelope(leap: np.ndarray, t: np.ndarray) -> dict:
    best = None
    for b in B_GRID:
        a = float(np.max(leap - b * t)) if len(leap) else 0.0
        mean_allowed = float(np.mean(a + b * t)) if len(t) else 0.0
        if best is None or mean_allowed < best["mean_allowed"]:
            best = {"a": a, "b": b, "mean_allowed": mean_allowed}
    return best


def cmd_measure(a):
    sub = "measure" if a.span_for_move == 24 else f"measure_span{a.span_for_move}"
    (OUT / sub).mkdir(parents=True, exist_ok=True)
    files = sorted(str(p) for p in LIEDER.rglob("*.mxl"))[: a.limit]
    with Pool(a.workers) as pool:
        res = pool.map(measure_file, [(f, a.span_for_move, sub) for f in files], chunksize=1)
    st = {}
    for r in res:
        st[r["status"].split(":")[0]] = st.get(r["status"].split(":")[0], 0) + 1
    print(json.dumps({"files": len(files), "status": st}), flush=True)


def cmd_fit(a):
    sub = "measure" if a.span_for_move == 24 else f"measure_span{a.span_for_move}"
    rows = [json.loads(p.read_text()) for p in sorted((OUT / sub).glob("*.json"))]
    ok = [r for r in rows if r["status"] == "ok"]
    out = {"files": len(rows), "ok": len(ok), "dev_files": sum(r["dev"] for r in ok),
           "status": {}, "source": "OpenScore Lieder (CC0), piano part, repeats not expanded, grace notes excluded"}
    for r in rows:
        k = r["status"].split(":")[0]
        out["status"][k] = out["status"].get(k, 0) + 1
    for kind in ("sounding", "struck"):
        sp = {d: np.array([s for r in ok if r["dev"] == d for s in r[f"span_{kind}"] if s >= 0]) for d in (True, False)}
        nos = {d: sum(1 for r in ok if r["dev"] == d for s in r[f"span_{kind}"] if s == -1) for d in (True, False)}
        allsets = {d: sum(1 for r in ok if r["dev"] == d for s in r[f"span_{kind}"] if s != -2) for d in (True, False)}
        dev_max = int(sp[True].max())
        res = {"dev_max": dev_max,
               "dev_percentiles": {q: float(np.percentile(sp[True], q)) for q in (50, 90, 99, 99.9)},
               "heldout_share_above": {v: float((sp[False] > v).mean()) for v in (12, 14, 16, 19, 24, dev_max)},
               "no_two_hand_split_share": {"dev": nos[True] / max(1, allsets[True]), "heldout": nos[False] / max(1, allsets[False])}}
        mv = {d: np.array([(m, g) for r in ok if r["dev"] == d for m, g in r[f"move_{kind}"] if m >= 0]) for d in (True, False)}
        env = fit_envelope(mv[True][:, 0], mv[True][:, 1])
        ho = mv[False]
        env["heldout_fail_share"] = float((ho[:, 0] > env["a"] + env["b"] * ho[:, 1]).mean())
        env["placeholder_U12_U13_heldout_fail_share"] = float((ho[:, 0] > 24 + 12 * ho[:, 1]).mean())
        env["dev_move_percentiles_at_gap_le_quarter"] = {q: float(np.percentile(mv[True][mv[True][:, 1] <= 1, 0], q))
                                                         for q in (50, 90, 99, 99.9)}
        res["hand_leap"] = env
        out[kind] = res
    OUT.mkdir(parents=True, exist_ok=True)
    out["span_for_move"] = a.span_for_move
    (OUT / ("piano.json" if a.span_for_move == 24 else f"piano_span{a.span_for_move}.json")).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--workers", type=int, default=16)
    m.add_argument("--limit", type=int, default=None)
    m.add_argument("--span-for-move", type=int, default=24)
    m8 = sub.add_parser("measure8")
    m8.add_argument("--workers", type=int, default=16)
    m8.add_argument("--limit", type=int, default=None)
    sub.add_parser("fit8")
    f = sub.add_parser("fit")
    f.add_argument("--span-for-move", type=int, default=24)
    a = ap.parse_args(argv)
    {"measure": cmd_measure, "fit": cmd_fit, "measure8": cmd_measure8, "fit8": cmd_fit8}[a.cmd](a)


if __name__ == "__main__":
    main()
