# Scratch: on the same cells, does the network's changed-games count look like a calibration arm's? (rank corr. + levels)
import json, numpy as np
from scipy.stats import spearmanr
R = '<svg_training>/runs/'
PASS = {'guard': {'guard_parked_ring', 'guard_mark_edge'}, 'strike': {'strike_straight', 'strike_high', 'strike_low'}}
for side in ['guard', 'strike']:
    t94 = json.load(open(R + f'2026-11-26_ste_ls12_read_{side}/results.json'))
    cal = json.load(open(R + f'2026-11-25_ste_ls15_calibration_{side}/results.json'))
    net = {(tuple(c['codes']), c['opponent']): c['flips'] for c in t94['cells'] if c['arm'] == 'net' and c['kind'] != 'info'}
    arms = {}
    for c in cal['cells']:
        if c['kind'] == 'info': continue
        arms.setdefault(c['arm'], {})[(tuple(c['codes']), c['opponent'])] = c['flips']
    print('\n==', side, 'net cells', len(net))
    for subset in ('all', 'passing-only'):
        keys = [k for k in net if subset == 'all' or set(k[0]) <= PASS[side]]
        print(f' {subset}: {len(keys)} cells; net flips median {np.median([net[k] for k in keys])}, max {max(net[k] for k in keys)}')
        for a in ['noise=0.02', 'noise=0.05', 'noise=0.1', 'bias=0.01', 'bias=0.02', 'turn=1.5', 'turn=3.0', 'scale=0.95']:
            ks = [k for k in keys if k in arms[a]]
            x = np.array([net[k] for k in ks]); y = np.array([arms[a][k] for k in ks])
            print(f'   v {a:11s} n {len(ks):3d} spearman {spearmanr(x, y).correlation:+.2f}  arm median {np.median(y):5.1f} max {y.max():3d} | net/arm median ratio {np.median(x)/max(np.median(y),1):.2f}')
    # cell sensitivity stability between arms (do the same cells top every arm?)
    keys = list(arms['noise=0.05'])
    def top(a, n=10): return set(sorted(keys, key=lambda k: -arms[a].get(k, 0))[:n])
    tn = set(sorted(net, key=lambda k: -net[k])[:10])
    print('  top-10 overlap: noise0.05 v bias0.02', len(top('noise=0.05') & top('bias=0.02')), '; noise0.05 v turn3', len(top('noise=0.05') & top('turn=3.0')),
          '; net v noise0.05', len(tn & top('noise=0.05')), '; net v bias0.02', len(tn & top('bias=0.02')), '; net v turn3', len(tn & top('turn=3.0')))
    print('  spearman noise0.05 v noise0.1 (same cells):', round(spearmanr([arms['noise=0.05'][k] for k in keys], [arms['noise=0.1'][k] for k in keys]).correlation, 2),
          '; bias0.02 v turn3:', round(spearmanr([arms['bias=0.02'][k] for k in keys], [arms['turn=3.0'][k] for k in keys]).correlation, 2))
    # by opponent: mean flips per opponent for net and arms
    opps = sorted({k[1] for k in keys})
    for a in ['noise=0.05', 'bias=0.02', 'turn=3.0']:
        print(f'  mean flips by opponent {a:10s}', {o.split("_",1)[1]: round(np.mean([arms[a][k] for k in keys if k[1]==o]),1) for o in opps})
    print(f'  mean flips by opponent {"net":10s}', {o.split("_",1)[1]: round(np.mean([net[k] for k in net if k[1]==o]),1) for o in opps})
