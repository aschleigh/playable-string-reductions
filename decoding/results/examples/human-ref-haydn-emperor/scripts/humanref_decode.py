import json, math, sys
from fractions import Fraction as F
import torch
sys.path.insert(0, "/scratch/ashleyz/reduction_ladder")
import model.augment as A
from model.decode import decode_movement, TPQ_BASE
from model.net import Arranger
from arrangement.instruments import load_ensemble
d = next(json.loads(l) for l in open("model/data/train.jsonl") if "Op.76_No.3" in l and json.loads(l)["key"].endswith("m02"))
src = [(int(p), F(o), F(du), int(x)) for p, o, du, x in d["notes"] if F(o) < 80]
src = [(p, o, min(du, 80 - o), x) for p, o, du, x in src]
tpq = TPQ_BASE * math.lcm(1, *{x.denominator for n in src for x in (n[1], n[2])})
ens = load_ensemble("piano"); insts = [i.key for i in ens.instruments]
out = {"source": [[p, str(o), str(du), x] for p, o, du, x in src]}
for run in ("control-FK2", "control-FK3"):
    ck = torch.load(f"model/results/rl/{run}/checkpoint.pt", map_location="cpu")
    net = Arranger(**ck["cfg"]["net"]).eval(); net.load_state_dict(ck["model"])
    inotes, com = decode_movement(net, "cpu", src, insts, ens, True, tpq, melody_first=True)
    out[run] = [[p, str(o), str(du), x] for p, o, du, x in A.expand(inotes)]
    print(run, len(out[run]), "notes; interventions", com.n_intervened)
json.dump(out, open("/scratch/shared/ashleyz/tmp/claude-28774/-scratch-ashleyz-reduction-ladder/12f0879f-f358-4ec2-87f0-8ae62a6655a1/scratchpad/humanref_decoded.json", "w"))
