"""GRPO for solo flute and piano from control-FK2 (BLOCK6 Amendment A1, R73). Run before any Amendment A run.

1. the joint-option layout follows the checkpoint's realisation count (n_real 6: CUT, DROP id 120);
2. ratio identity and replay determinism, as tests/test_grpo.py, for both one-part ensembles, with CUT;
3. a CUT label ends its note at the movement's CUT point;
4. the A2 reward: the F3 / K target itself sits on no floor and no CUT guard; the breath term is the run excess;
5. longest_run matches model/dev_fk.py's definition.
Needs torch, the control-FK2 checkpoint and targets_fk2 (skipped otherwise)."""
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import model.augment as A  # noqa: E402
import model.grpo as G  # noqa: E402

CK = Path(__file__).resolve().parents[1] / "model" / "results" / "rl" / "control-FK2" / "checkpoint.pt"
pytestmark = pytest.mark.skipif(not (CK.exists() and (G.RL / "targets_fk2__train.pkl").exists()),
                                reason="control-FK2 checkpoint or targets_fk2 missing")
REG = ("solo_flute", "piano")
_cache = {}


def _fk(fn):
    """Run with the n_real 6 layout and restore the default afterwards (tests/test_grpo.py assumes 5)."""
    def wrapped():
        G.configure(6)
        try:
            fn()
        finally:
            G.configure(5)
    wrapped.__name__ = fn.__name__
    return wrapped


def _setup():
    if _cache:
        return _cache["net"], _cache["m"], _cache["w0"]
    from arrangement.instruments import load_ensemble
    from model.decode import decode_movement
    from model.net import Arranger
    torch.set_num_threads(4)
    ck = torch.load(CK, map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).eval()
    net.load_state_dict(ck["model"])
    assert net.n_real == 6
    mvs = sorted(G.load_split("train"), key=lambda m: len(m.src))
    m = next(x for x in mvs if len(x.src) > 300)
    for r in REG:
        ens = load_ensemble(r)
        inotes, _ = decode_movement(net, "cpu", m.src, [i.key for i in ens.instruments], ens, True, m.tpq, True)
        m.ctx[r] = [(n.part, n.octave, n.real) for n in inotes]
    ws = G.windows(m, 384)
    w0 = max(ws[1:] or ws, key=lambda w: sum(1 for n in m.src if w <= n[1] < w + A.WINDOW))
    _cache.update(net=net, m=m, w0=w0)
    return net, m, w0


def _rollouts(regime, n=4):
    net, m, w0 = _setup()
    if regime not in _cache:
        rng = np.random.default_rng(0)
        _cache[regime] = [G.rollout(net, m, regime, w0, rng) for _ in range(n)]
    return _cache[regime]


@_fk
def test_joint_layout_n_real_6():
    assert G.N_REAL == 6 and G.DROP_ID == G.N_JOINT == 120
    for pc in range(4):
        for o in range(5):
            for r in range(6):
                assert G.decode_id(G.joint_id(pc, o, r)) == (pc, o, r)
    assert G._labels(G.DROP_ID)[0] == A.DROP
    assert G._labels(G.joint_id(0, 2, A.CUT)) == (0, 0, A.CUT)


@_fk
def test_fk_ratio_identity_and_replay():
    from arrangement.instruments import load_ensemble
    net, m, w0 = _setup()
    for r in REG:
        trs = _rollouts(r)
        with torch.no_grad():
            lp, _ = G.policy_terms(net, trs, "cpu")
        assert np.abs(lp.numpy() - np.concatenate([t.logp_old for t in trs])).max() < 1e-4, r
        ens = load_ensemble(r)
        for tr in trs:
            idx, inotes, com, win, todo = G._setup_window(m, r, w0, ens)
            for d in range(len(tr.chosen)):
                k = win[int(tr.dec_pos[d])]
                mk = np.array([com.probe(k, inotes, *G._labels(int(a))) for a in tr.cands[d]], bool)
                assert np.array_equal(mk, tr.masks[d]), f"{r}: mask differs at decision {d}"
                assert com.try_commit(k, inotes, *G._labels(int(tr.cands[d][tr.chosen[d]])))
            assert sorted(A.expand([inotes[k] for k in todo])) == sorted(tr.out_notes), r
    blocked = np.concatenate([[not mk.all() for mk in t.masks] for t in _rollouts("solo_flute")])
    assert blocked.any(), "flute window has no blocked candidate"


@_fk
def test_cut_ends_at_cut_point():
    _, m, w0 = _setup()
    seen = 0
    for tr in _rollouts("solo_flute"):
        outs = {(o, x): d for _, o, d, x in tr.out_notes}
        for i, lab in zip(tr.parts["_src_idx"], tr.labels):
            if lab[0] != A.DROP and lab[2] == A.CUT:
                _, o, d, x = m.src[i]
                key = (o, x + lab[1])
                if key in outs:
                    assert outs[key] == m.cut[i][0] - o
                    seen += 1
    assert seen > 0, "no CUT sampled in the flute rollouts"


@_fk
def test_target_has_no_floor_or_guard_penalty():
    _, m, w0 = _setup()
    for r, s in (("solo_flute", "F05"), ("piano", "K")):
        tag, key = G.TARGETS[r]
        labs = G._TARGET_LABELS.get(tag) or __import__("pickle").load(open(G.RL / f"targets_{tag}__train.pkl", "rb"))
        labs = labs[m.key][key]
        notes = [A.INote(o, d, x, part=p, octave=oc, real=re, src=sp, cut_end=m.cut[i][0], cut_kind=m.cut[i][1])
                 for i, ((sp, o, d, x), (p, oc, re)) in enumerate(zip(m.src, labs))]
        win = [i for i, n in enumerate(notes) if w0 <= n.onset < w0 + A.WINDOW]
        ctx = [n for n in notes if w0 - A.CONTEXT <= n.onset < w0 or (n.onset < w0 - A.CONTEXT and n.onset + n.dur > w0 - A.CONTEXT)]
        tr = G.Trajectory([], np.zeros(0, np.int64), np.zeros(0, np.int64), [], [], np.zeros(0, np.int64),
                          np.zeros(0), np.zeros(0, bool), [labs[i] for i in win], A.expand([notes[i] for i in win]))
        tr.parts["_ctx_notes"] = A.expand(ctx)
        out = G.window_reward(m, r, w0, tr, G.SETTINGS[s])
        assert out["G"] == 0.0, (r, out)
        if r == "solo_flute":
            assert out["C"] == 0.0 and out["B"] == max(0.0, out["run_q"] - 12) / 16
        assert np.isfinite(out["R"])
    for r, s in (("solo_flute", "F10"), ("piano", "K")):
        for tr in _rollouts(r):
            out = G.window_reward(m, r, w0, tr, G.SETTINGS[s])
            assert np.isfinite(out["R"]) and 0 <= out["Fw"] <= 1


def test_longest_run():
    n = lambda o, d: (0, F(o), F(d), 72)
    notes = [n(0, 1), n(1, 1), n(2, 2), n(F(9, 2), 1), n(F(11, 2), 3)]      # runs 0-4 and 4.5-8.5 (rest 1/2)
    assert G.longest_run(notes, F(0), F(16)) == 4.0
    notes2 = [n(0, 1), n(F(5, 4), 1), n(F(9, 4), 1)]                           # rests of 1/4 do not break
    assert G.longest_run(notes2, F(0), F(16)) == 3.25
    assert G.longest_run(notes, F(5), F(16)) == 4.0                           # only runs overlapping [lo, hi)
    assert G.longest_run(notes[:3], F(5), F(16)) == 0.0
