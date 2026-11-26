from common import *
torch.set_num_threads(2)
net, p = load_net("strike")
te = load_round("strike", 2, n=200000, seed=7)
out = net_all(net, te["obs"], te["slot"])
print({s[7:]: round(rmse(out[:, i, :2] - te["label"][:, i, :2]), 4) for i, s in enumerate(STRIKES)})
