import json, numpy as np
R='<svg_training>/runs/'
for side in ['guard','strike']:
    d=json.load(open(R+f'2026-11-25_ste_ls15_calibration_{side}/results.json'))
    print('\n==',side)
    arms=d['arms']
    for name,a in arms.items():
        cs=[c for c in d['cells'] if c['arm']==name and c['kind']!='info']
        if not cs: print(f'{name:32s} no gated cells'); continue
        f=np.array([c['flips'] for c in cs]); net=np.array([abs(c['b']-c['c']) for c in cs])
        ciout=sum(1 for c in cs if c['ci_adjusted'][0]<-0.045 or c['ci_adjusted'][1]>0.045)
        # rmse
        rm=0
        for s,e in a.get('errors',{}).get('skills',{}).items():
            act=e.get('active') or [True]*4; r=[x for x,ac in zip(e.get('rmse') or [],act) if ac]
            if r: rm=max(rm,max(r))
        p=a['pooled']['all']
        print(f"{name:32s} kind={a['kind']:8s} size={a['size']} ch={a['channels']} cells={len(cs):3d} med={np.median(f):5.1f} p90={np.percentile(f,90):5.1f} max={f.max():4d} n>30={int((f>30).sum()):3d} n>20={int((f>20).sum()):3d} ci_out={ciout} pooled={p['diff']:+.4f} [{p['ci'][0]:+.4f},{p['ci'][1]:+.4f}] rmse={rm:.4f}")
