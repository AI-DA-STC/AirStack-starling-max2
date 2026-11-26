# Scratch: which cheap measure predicts a cell's changed games (flips) in the T94 read?
# Pairs each net cell with its scripts cell (same codes, opponent, starts) from games/*.npz; per game: flip
# (side's win differs), path divergence at 1, 3, 10 s (largest over drones live in both).
import json, numpy as np, collections
from scipy.stats import spearmanr
R = '<svg_training>/runs/'
for side in ['guard', 'strike']:
    rd = R + f'2026-11-26_ste_ls12_read_{side}/'
    res = json.load(open(rd + 'results.json')); lay = json.load(open(rd + 'layout.json'))
    skill_rmse = {k: max(v['rmse'][:2]) for k, v in res['errors']['skills'].items()}
    # locate every (arm, codes, opponent) -> (file, row offset)
    loc = {}
    for b in lay['batches']:
        for j, c in enumerate(b['cells']):
            loc[(b['arm'], tuple(c['codes']), c['opponent'])] = (b['name'], j)
    print('\n==', side, 'arms in layout', collections.Counter(b['arm'] for b in lay['batches']))
    cache = {}
    def get(name):
        if name not in cache: cache[name] = dict(np.load(rd + f'games/{name}.npz'))
        return cache[name]
    rows = []
    allg = []
    for c in res['cells']:
        if c['arm'] != 'net' or c['kind'] == 'info': continue
        key = (tuple(c['codes']), c['opponent'])
        ref_arm = 'scripts'
        if (ref_arm,) + key not in loc: print('no ref', key); continue
        fa, ja = c['games']['file'].split('/')[-1][:-4], c['games']['start']
        fr, jr = loc[(ref_arm,) + key]
        A = get(fa); B = get(fr); n = 1000
        sa = slice(ja, ja + n); sb = slice(jr * n, jr * n + n)
        win = 1 if side == 'guard' else 2
        oa, ob = A['outcome'][sa], B['outcome'][sb]
        # infer win code: count flips under both codes and pick matching
        flips = {w: int(((oa == w) != (ob == w)).sum()) for w in np.unique(np.concatenate([oa, ob]))}
        assert (A['start_pos_m'][sa] == B['start_pos_m'][sb]).all()
        both = A['alive_at'][sa] & B['alive_at'][sb]
        d = np.linalg.norm(A['pos_at'][sa] - B['pos_at'][sb], axis=-1)
        dg = np.where(both, d, -np.inf).max(1)  # [games, marks]
        rows.append(dict(c=c, flips=c['flips'], fl=flips, dg=dg, endd=int((A['end_step'][sa] != B['end_step'][sb]).sum()),
                         rm_mean=np.mean([skill_rmse[k] for k in c['codes']]), rm_max=max(skill_rmse[k] for k in c['codes'])))
        fg = None
        allg.append((dg, c['flips']))
    # check flip inference
    bad = [r for r in rows if r['flips'] not in r['fl'].values()]
    print('cells', len(rows), 'flip code mismatches', len(bad), 'example', rows[0]['fl'], rows[0]['flips'])
    F = np.array([r['flips'] for r in rows])
    preds = {'open-loop mean skill RMSE': [r['rm_mean'] for r in rows], 'open-loop max skill RMSE': [r['rm_max'] for r in rows],
             'games whose end tick differs': [r['endd'] for r in rows]}
    for j, t in enumerate(['1s', '3s', '10s']):
        for thr in (0.01, 0.05, 0.2, 0.5):
            preds[f'share games diverged >{thr} m at {t}'] = [float((r['dg'][:, j] > thr).sum()) for r in rows]
        preds[f'p90 divergence at {t}'] = [float(np.percentile(r['dg'][:, j][np.isfinite(r['dg'][:, j])], 90)) if np.isfinite(r['dg'][:, j]).any() else 0 for r in rows]
        preds[f'games still compared at {t}'] = [float(np.isfinite(r['dg'][:, j]).sum()) for r in rows]
    for k, v in preds.items():
        rho = spearmanr(v, F).correlation
        print(f'  spearman {rho:+.2f}  {k}')
    # within passing-only cells
    PASS = {'guard': {'guard_parked_ring', 'guard_mark_edge'}, 'strike': {'strike_straight', 'strike_high', 'strike_low'}}[side]
    idx = [i for i, r in enumerate(rows) if set(r['c']['codes']) <= PASS]
    if len(idx) > 5:
        print('  passing-only cells', len(idx))
        for k in ['games whose end tick differs', 'share games diverged >0.05 m at 3s', 'share games diverged >0.2 m at 3s', 'share games diverged >0.05 m at 10s', 'p90 divergence at 3s', 'open-loop mean skill RMSE']:
            print(f'    spearman {spearmanr([preds[k][i] for i in idx], F[idx]).correlation:+.2f} {k}')
    # games end when? share of games ended by 1/3/10 s in scripts arm
    ends = np.concatenate([get(loc[('scripts', tuple(r['c']['codes']), r['c']['opponent'])][0])['end_step'] for r in rows[:30]])
    print('  scripts end_step quantiles (ticks)', np.percentile(ends, [10, 50, 90]).round(), 'game_ticks', get(rows[0]['c']['games']['file'].split('/')[-1][:-4])['game_ticks'])
    # game-level: P(flip | diverged) by mark
    print('  example worst cells:')
    for r in sorted(rows, key=lambda r: -r['flips'])[:5]:
        print('    flips', r['flips'], 'endd', r['endd'], 'diverged>0.05 at 1/3/10s', [(int((r['dg'][:, j] > 0.05).sum())) for j in range(3)], ','.join(r['c']['codes']), r['c']['opponent'])
