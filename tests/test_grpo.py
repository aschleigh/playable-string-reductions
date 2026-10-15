"""GRPO masking-ratio tests (BLOCK4.md 2c). Run before any real RL run.

1. ratio identity: with no update, the learner's masked log-prob equals the rollout's (every
   decision, including notes whose top option was blocked);
2. replay determinism: replaying the stored decisions through a fresh checker reproduces every
   stored mask bit and the output;
3. masked sampling matches p*M / sum(p*M) (chi-square);
4. masked-out candidates do not enter the learner's log-prob (adding one changes nothing);
5. the classic bug (renormalising over the unmasked candidates) breaks test 1 on blocked notes.
Needs torch and the arranger-v2b checkpoint (skipped otherwise)."""
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import model.augment as A  # noqa: E402
import model.grpo as G  # noqa: E402

CK = Path(__file__).resolve().parents[1] / "model" / "results" / "arranger-v2b" / "checkpoint.pt"
pytestmark = pytest.mark.skipif(not CK.exists(), reason="arranger-v2b checkpoint missing")

_cache = {}


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
    mvs = sorted(G.load_split("val"), key=lambda m: len(m.src))
    m = next(x for x in mvs if len(x.src) > 300)
    ens = load_ensemble("trio")
    inotes, _ = decode_movement(net, "cpu", m.src, [i.key for i in ens.instruments], ens, True, m.tpq)
    m.ctx["trio"] = [(n.part, n.octave, n.real) for n in inotes]
    # a dense window, so some top options are blocked
    ws = G.windows(m, 384)
    w0 = max(ws[1:] or ws, key=lambda w: sum(1 for n in m.src if w <= n[1] < w + A.WINDOW))
    _cache.update(net=net, m=m, w0=w0)
    return net, m, w0


def _rollouts(n=4):
    net, m, w0 = _setup()
    if "trs" not in _cache:
        rng = np.random.default_rng(0)
        _cache["trs"] = [G.rollout(net, m, "trio", w0, rng) for _ in range(n)]
    return _cache["trs"]


def test_ratio_identity_including_blocked_notes():
    net, _, _ = _setup()
    trs = _rollouts()
    with torch.no_grad():
        lp, _ = G.policy_terms(net, trs, "cpu")
        lp1, _ = G.policy_terms(net, trs[:1], "cpu", chunk=1)
    old = np.concatenate([t.logp_old for t in trs])
    # batched + padded float32 forward: ratio within 1e-4 of 1; unbatched: exact to float32 (1e-6)
    assert np.abs(lp.numpy() - old).max() < 1e-4
    assert np.abs(lp1.numpy() - trs[0].logp_old).max() < 1e-6
    blocked = np.concatenate([[not m.all() for m in t.masks] for t in trs])
    assert blocked.any(), "test window has no blocked candidate; pick a denser one"


def test_replay_reproduces_masks_and_output():
    _, m, w0 = _setup()
    from arrangement.instruments import load_ensemble
    ens = load_ensemble("trio")
    for tr in _rollouts():
        idx, inotes, com, win, todo = G._setup_window(m, "trio", w0, ens)
        for d in range(len(tr.chosen)):
            k = win[int(tr.dec_pos[d])]
            mk = np.array([com.probe(k, inotes, *G._labels(int(a))) for a in tr.cands[d]], bool)
            assert np.array_equal(mk, tr.masks[d]), f"mask differs at decision {d}"
            assert com.try_commit(k, inotes, *G._labels(int(tr.cands[d][tr.chosen[d]])))
        assert sorted(A.expand([inotes[k] for k in todo])) == sorted(tr.out_notes)


def test_masked_sampling_distribution():
    rng = np.random.default_rng(1)
    jl = np.log(np.array([0.5, 0.2, 0.15, 0.1, 0.05]))
    mk = np.array([True, False, True, True, False])
    n = 100_000
    counts = np.bincount([G.sample_masked(jl, mk, rng) for _ in range(n)], minlength=5)
    p = np.where(mk, np.exp(jl), 0); p /= p.sum()
    assert counts[~mk].sum() == 0
    exp = n * p[mk]
    chi2 = ((counts[mk] - exp) ** 2 / exp).sum()
    assert chi2 < 13.8          # chi-square, 2 dof, p = 0.001


def test_masked_out_candidates_do_not_enter_logp():
    net, _, _ = _setup()
    trs = _rollouts()
    with torch.no_grad():
        lp, _ = G.policy_terms(net, trs, "cpu")
    import copy
    trs2 = copy.deepcopy(trs)
    for t in trs2:
        for d in range(len(t.cands)):
            extra = next(a for a in range(100) if a not in set(t.cands[d].tolist()))
            t.cands[d] = np.append(t.cands[d], extra)
            t.masks[d] = np.append(t.masks[d], False)
    with torch.no_grad():
        lp2, _ = G.policy_terms(net, trs2, "cpu")
    assert torch.allclose(lp, lp2, atol=1e-12)


def test_mask_unaware_ratio_fails_on_blocked_notes():
    net, _, _ = _setup()
    import copy
    trs = copy.deepcopy(_rollouts())
    blocked = np.concatenate([[not m.all() for m in t.masks] for t in trs])
    for t in trs:
        t.masks = [np.ones_like(m) for m in t.masks]      # the bug: renormalise over everything
    with torch.no_grad():
        lp, _ = G.policy_terms(net, trs, "cpu")
    old = np.concatenate([t.logp_old for t in trs])
    diff = np.abs(lp.numpy() - old)
    assert diff[blocked].max() > 1e-2 and diff[~blocked].max() < 1e-4


def test_microbatch_accumulation_equals_full_batch():
    net, _, _ = _setup()
    trs = _rollouts()
    adv = np.array([1.0, -0.5, 0.25, -0.75])
    grads = []
    for micro in (len(trs), 1):
        net.zero_grad(set_to_none=True)
        G.accumulate_grads(net, net, trs, adv, "cpu", 0.2, 0.02, micro)
        grads.append(torch.cat([p.grad.flatten() for p in net.parameters() if p.grad is not None]))
    assert torch.allclose(grads[0], grads[1], rtol=1e-4, atol=1e-7)


def test_lockstep_engine_matches_sequential_rollouts():
    """The batched-forward engine gives the same trajectories as per-rollout forwards (same seeds)."""
    ctx_files = list((G.RL / "contexts").glob("arranger-v2b__train.*.pkl"))
    if not ctx_files:
        pytest.importorskip("no_contexts_available")
    net, _, _ = _setup()
    mvs = [m for m in G.attach_contexts(G.load_split("train"), "arranger-v2b") if "trio" in m.ctx]
    m = min(mvs, key=lambda x: len(x.src))
    ws = G.windows(m, 384)[:2]
    jobs = [(m.key, "trio", w0, 100 + i) for i, w0 in enumerate(ws) for _ in range(2)]
    eng = G.LockstepEngine(2, "arranger-v2b", "A")
    try:
        trs, _ = eng.run(net, "cpu", jobs)
    finally:
        eng.close()
    for (k, r, w0, seed), tr in zip(jobs, trs):
        ref = G.rollout(net, m, r, w0, np.random.default_rng(seed))
        assert np.array_equal(tr.chosen, ref.chosen) and sorted(tr.out_notes) == sorted(ref.out_notes)
        assert np.abs(tr.logp_old - ref.logp_old).max() < 1e-4
    with torch.no_grad():
        lp, _ = G.policy_terms(net, trs, "cpu")
    assert np.abs(lp.numpy() - np.concatenate([t.logp_old for t in trs])).max() < 1e-4
