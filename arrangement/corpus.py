"""Corpus preparation: parse every movement once, keep the parts the target
ensemble can play, cache as JSON.

    python -m arrangement.corpus [--workers N] [--limit K]

Reads raw_corpora/StringQuartets/scores/**/*.mxl (OpenScore, CC0; approved
decision 7: ABC unused). Parsing is slow (~20 s per multi-movement file), so
everything downstream reads the cache in cache/arrangement/openscore/.
Parts whose declared name matches no configured instrument, or matches the
ensemble's exclude_part_names (Berg Op.3 "Klang" ossia staves), are dropped
and recorded in the manifest.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
import traceback
from functools import partial
from dataclasses import asdict, replace
from multiprocessing import Pool
from pathlib import Path

import re

from arrangement.instruments import load_ensemble, load_instruments
from arrangement.parse import DeclaredPart, NoteEvent, ParsedPiece, load_raw_score, movement_index_ranges, parse_score
from arrangement.spec import extract_spec
from arrangement.ties import TieAnomaly

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_corpora" / "StringQuartets" / "scores"
CACHE = ROOT / "cache" / "arrangement" / "openscore"
log = logging.getLogger(__name__)

_EVENT_FIELDS = [f for f in NoteEvent.__dataclass_fields__]


def select_parts(piece: ParsedPiece, keep: list[int]) -> ParsedPiece:
    """Piece restricted to the given part ids, renumbered 0..k-1 in order;
    event ids renumbered densely in the original order."""
    remap = {old: new for new, old in enumerate(keep)}
    parts = [replace(p, part_id=remap[p.part_id]) for p in piece.parts if p.part_id in remap]
    events = []
    for e in piece.events:
        if e.part_id in remap:
            events.append(replace(e, id=len(events), part_id=remap[e.part_id]))
    return replace(piece, parts=parts, events=events)


def piece_to_json(piece: ParsedPiece) -> dict:
    return {
        "source": piece.source, "movement": piece.movement, "source_format": piece.source_format,
        "total_duration": piece.total_duration, "repeats_expanded": piece.repeats_expanded,
        "parts": [asdict(p) for p in piece.parts],
        "event_fields": _EVENT_FIELDS,
        "events": [[getattr(e, f) for f in _EVENT_FIELDS] for e in piece.events],
        "excluded": piece.excluded, "warnings": piece.warnings,
        "tie_anomalies": [{k: v for k, v in vars(a).items() if isinstance(v, (int, float, str, bool, type(None)))}
                          for a in piece.tie_anomalies],
    }


def piece_from_json(d: dict) -> ParsedPiece:
    fields = d["event_fields"]
    events = [NoteEvent(**dict(zip(fields, row))) for row in d["events"]]
    return ParsedPiece(source=d["source"], events=events, parts=[DeclaredPart(**p) for p in d["parts"]],
                       total_duration=d["total_duration"], repeats_expanded=d["repeats_expanded"],
                       excluded=d["excluded"], tie_anomalies=[], warnings=d["warnings"],
                       source_format=d["source_format"], movement=d["movement"])


def movement_key(path: Path, movement: int) -> str:
    rel = path.relative_to(RAW)
    return f"{rel.parts[0]}__{rel.parts[1]}__{path.stem}__m{movement:02d}".replace(" ", "_")


def load_cached(key: str, cache: Path = CACHE) -> ParsedPiece:
    return piece_from_json(json.loads((cache / f"{key}.json").read_text()))


def manifest(cache: Path = CACHE) -> list[dict]:
    p = cache / "manifest.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def prepare_file(path: str, cache: str = str(CACHE)) -> list[dict]:
    path_, cache_ = Path(path), Path(cache)
    instruments = load_instruments()
    excl = load_ensemble("quartet").exclude_part_names
    rows: list[dict] = []
    t0 = time.time()
    try:
        raw = load_raw_score(path_)
        ranges = movement_index_ranges(raw)
    except Exception as e:
        return [{"file": str(path_.relative_to(ROOT)), "movement": None, "status": "load_error",
                 "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=3)}]
    for m in range(1, len(ranges) + 1):
        row = {"file": str(path_.relative_to(ROOT)), "movement": m, "n_measures": ranges[m - 1][1] - ranges[m - 1][0]}
        try:
            piece = parse_score(path_, movement=m, score=raw)
            spec = extract_spec(piece, instruments)
            def playable(p):
                return p.instrument is not None and not any(re.search(x, p.name, re.I) for x in excl)
            keep = [p.part_id for p in spec.parts if playable(p)]
            dropped = [{"name": p.name, "notes": p.n_notes, "instrument": p.instrument}
                       for p in spec.parts if not playable(p)]
            piece = select_parts(piece, keep)
            key = movement_key(path_, m)
            (cache_ / f"{key}.json").write_text(json.dumps(piece_to_json(piece)))
            row.update(status="ok", key=key, n_notes=len(piece.events),
                       instruments=[p.instrument for p in spec.parts if playable(p)],
                       dropped_parts=dropped, n_warnings=len(piece.warnings),
                       repeats_expanded=piece.repeats_expanded, tie_anomalies=len(piece.tie_anomalies),
                       excluded=piece.excluded)
        except Exception as e:
            row.update(status="parse_error", error=f"{type(e).__name__}: {e}",
                       trace=traceback.format_exc(limit=3))
        rows.append(row)
    for r in rows:
        r["file_seconds"] = round(time.time() - t0, 1)
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cache", default=str(CACHE))
    args = ap.parse_args(argv)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted(str(p) for p in RAW.glob("*/*/*.mxl"))[: args.limit]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    log.info("preparing %d files with %d workers -> %s", len(files), args.workers, cache)
    out = cache / "manifest.jsonl"
    n_ok = 0
    with Pool(args.workers, maxtasksperchild=4) as pool, out.open("w") as fh:
        for k, rows in enumerate(pool.imap_unordered(partial(prepare_file, cache=str(cache)), files, chunksize=1)):
            for r in rows:
                fh.write(json.dumps(r) + "\n")
                n_ok += r["status"] == "ok"
            fh.flush()
            log.info("[%d/%d] %s: %d movements, %s", k + 1, len(files), rows[0]["file"], len(rows),
                     ",".join(sorted({r["status"] for r in rows})))
    log.info("done: %d movements ok", n_ok)


if __name__ == "__main__":
    main()
