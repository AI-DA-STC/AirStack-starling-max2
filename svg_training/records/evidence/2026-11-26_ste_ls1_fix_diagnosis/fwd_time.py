import time, torch
from common import *
torch.set_num_threads(6)
for w in (256, 512, 768, 1024):
    net = skill_net.SkillNet("strike", STRIKES, 3, 3, [w]*3, [6,7,10,11]).eval()
    obs = torch.randn(3000, OBS_DIM); obs[:, V.alive] = 1; slot = torch.randint(3, (3000,)); z = torch.randint(6, (3000,))
    with torch.no_grad():
        for _ in range(20): net(obs, slot, z)
        t = time.perf_counter()
        for _ in range(200): net(obs, slot, z)
    print(w, "ms per forward of 3000 rows: %.3f" % ((time.perf_counter() - t) / 200 * 1000), "params", sum(p.numel() for p in net.parameters()))
