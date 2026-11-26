from common import *
torch.set_num_threads(6)
net, p = load_net("strike")
print("meta", p["game_constants"], p["hidden"], p["zeroed_inputs"], p["team_size"], p["slot_width"])
for r in (0, 3):
    d = load_round("strike", r, n=400000, seed=r)
    obs, slot, lab = d["obs"], d["slot"], d["label"]
    out = net_all(net, obs, slot)
    err = out - lab
    print(f"\n=== round {r} kept rows sample {obs.shape[0]}; net_flown share {d['net_flown'].float().mean():.3f}")
    print("flown share:", {STRIKES[i]: round(float((d['flown']==i).float().mean()),3) for i in range(6)})
    for i, s in enumerate(STRIKES):
        print(f"  {s:18s} rmse xy {rmse(err[:, i, :2]):.4f}  (per ch {rmse(err[:,i,0]):.4f},{rmse(err[:,i,1]):.4f})  rows where flown {rmse(err[:, i, :2], d['flown']==i):.4f}")
    for i in (1, 4, 5):
        s = STRIKES[i]
        e = err[:, i, :2]
        print(f"  {s}: by n_live", {k: round(rmse(e, d['n_live']==k),4) for k in (1,2,3)},
              "near_switch", {b: round(rmse(e, d['near_switch']==b),4) for b in (True, False)},
              "mode", {m: round(rmse(e, d['mode']==j),4) for j, m in enumerate(('uniform','mix','random'))},
              "opp", {GUARDS[j][6:]: round(rmse(e, d['opponent']==j),4) for j in range(5)})
