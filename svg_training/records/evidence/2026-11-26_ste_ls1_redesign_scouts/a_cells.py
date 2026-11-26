import json, collections, numpy as np
R='<svg_training>/runs/'
PASS={'guard':{'guard_parked_ring','guard_mark_edge'},'strike':{'strike_straight','strike_high','strike_low'}}
PASS2={'guard':{'guard_parked_ring','guard_mark_edge','guard_parked_centre'},'strike':PASS['strike']}
for side in ['guard','strike']:
    d=json.load(open(R+f'2026-11-26_ste_ls12_read_{side}/results.json'))
    zc=d['intervals']['z_cell']; print('\n==',side,'z_cell',zc,'m',d['intervals']['m'])
    for arm in ['oracle','net','unfitted','permuted','noise','bias','rotate_deg']:
        cs=[c for c in d['cells'] if c['arm']==arm and c['kind']!='info']
        if not cs: continue
        f=np.array([c['flips'] for c in cs])
        print(f' arm {arm:10s} cells {len(cs):3d} flips median {np.median(f):5.1f} max {f.max():4d} >30: {(f>30).sum():3d}  ci-out: {sum(1 for c in cs if c["ci"][0]< -0.045 or c["ci"][1]>0.045)}')
    for lab,P in [('passing only',PASS[side]),('passing+parked_centre',PASS2[side])]:
        cs=[c for c in d['cells'] if c['arm']=='net' and c['kind']!='info' and set(c['codes'])<=P]
        f=np.array([c['flips'] for c in cs])
        print(f' net cells {lab}: {len(cs)}, flips median {np.median(f)}, max {f.max()}, >30 {(f>30).sum()}, ci-out {sum(1 for c in cs if c["ci"][0]< -0.045 or c["ci"][1]>0.045)}')
        for c in sorted(cs,key=lambda c:-c['flips'])[:10]:
            print('   ',c['flips'],'b',c['b'],'c',c['c'],','.join(x.split('_',1)[1] for x in c['codes']),'v',c['opponent'],'ci',[round(v,4) for v in c['ci']], 'kind',c['kind'])
    # INFO cells passing only
    cs=[c for c in d['cells'] if c['arm']=='net' and c['kind']=='info' and set(c['codes'])<=PASS[side]]
    if cs: print(' info passing-only', [(c['flips'],c['codes']) for c in cs])
    # synthetic arms detail
    for c in d['cells']:
        if c['arm'] not in ('net','oracle','unfitted','permuted'):
            print('  ctrl',c['arm'],c.get('batch'),c['kind'],','.join(c['codes']),'v',c['opponent'],'flips',c['flips'],'diff',round(c['diff'],4))
