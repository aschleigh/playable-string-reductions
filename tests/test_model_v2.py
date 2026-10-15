"""arranger-v2 changes (BLOCK4.md Step 3): source-part input feature and realisation class weights.
v1 checkpoints must load and behave exactly as before."""
import random
from fractions import Fraction as F

import pytest

torch = pytest.importorskip("torch")

import model.augment as A  # noqa: E402
from model.features import collate, encode  # noqa: E402
from model.net import Arranger  # noqa: E402
from model.train import losses  # noqa: E402

NOTES = [(sp, F(k), F(1), 60 + 4 * sp + (k % 3)) for sp in range(4) for k in range(24)]


def _batch():
    rng = random.Random(0)
    _, inotes, _ = A.make_example(NOTES, F(8), rng, A.load_ranges(), ensemble="trio", augment=False)
    return inotes, collate([encode(inotes, A.ENSEMBLES["trio"][0], F(8))])


def test_make_example_records_source_part():
    inotes, b = _batch()
    assert {n.src for n in inotes} == {0, 1, 2, 3}
    assert sorted(set(b["src"][0].tolist())) == [0, 1, 2, 3]


def test_unknown_source_part_encodes_as_4():
    b = collate([encode([A.INote(F(0), F(1), 60)], ["violin", "viola", "cello"], F(0))])
    assert b["src"].tolist() == [[4]]


def test_v1_net_ignores_src_and_loads_strict():
    torch.manual_seed(0)
    net = Arranger(d=32, layers=1, heads=4, ff=64, dropout=0.0).eval()
    assert not any(k.startswith("src") for k in net.state_dict())
    Arranger(d=32, layers=1, heads=4, ff=64).load_state_dict(net.state_dict(), strict=True)
    _, b = _batch()
    b2 = dict(b); b2["src"] = torch.full_like(b["src"], 4)
    with torch.no_grad():
        assert torch.equal(net(b)["part"], net(b2)["part"])


def test_v2_net_uses_src():
    torch.manual_seed(0)
    net = Arranger(d=32, layers=1, heads=4, ff=64, dropout=0.0, src_feature=True).eval()
    _, b = _batch()
    b2 = dict(b); b2["src"] = torch.full_like(b["src"], 4)
    with torch.no_grad():
        assert not torch.equal(net(b)["part"], net(b2)["part"])


def test_realisation_class_weights_change_only_realisation_loss():
    torch.manual_seed(0)
    net = Arranger(d=32, layers=1, heads=4, ff=64, dropout=0.0).eval()
    _, b = _batch()
    b["y_real"][0, :3] = torch.tensor([1, 2, 3])   # some non-plain targets
    with torch.no_grad():
        out = net(b)
        a = losses(out, b)
        w = losses(out, b, torch.tensor([1.0, 10.0, 10.0, 7.0, 1.0]))
    assert a[0] == w[0] and a[1] == w[1] and a[2] != w[2]
