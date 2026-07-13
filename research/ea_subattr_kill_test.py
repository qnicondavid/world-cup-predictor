#!/usr/bin/env python3
"""research/ea_subattr_kill_test.py - stage-1 incremental-value kill test for the EA
sub-attribute composites (frozen plan section 5; seal notes/model/ea_subattr_freeze.txt).

Decides ONLY gk_stop and the set-piece pair (sp_threat + sp_vuln). The other six composite
panels are printed for prioritization only, with no pass/kill authority.

Method (frozen): for each composite, leave-one-tournament-out residualize it jointly on the
two anchors z(log market value) and z(ovr_top26), OLS with intercept fit on the other 20
blocks, standardized within the training blocks, applied to the held-out block. Match feature
d = r_home - r_away (gk_stop and each probe), or (r_threat+r_vuln)_home minus the same for away
(the coupled pair). Correlate d with the value-only outcome residual 1/0.5/0 - (p_home+0.5 p_draw)
from ea_predictions_zero.csv over 768 matches: pooled, WC-128 and continental-640 strata,
per-block signs, and an anchor-overlap panel (corr vs each anchor, joint R^2, leftover 1-R^2).

Frozen thresholds: PASS pooled >= +0.07 with both macro strata positive; KILL pooled <= +0.03
or the strata opposite in sign; NEAR ZONE between. Reads composites from data/ea_ratings.csv.
Run: python3 research/ea_subattr_kill_test.py
"""
import csv, os
from collections import defaultdict
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EA = os.path.join(REPO, "data", "ea_ratings.csv")
MV = os.path.join(REPO, "data", "market_values.csv")
ZERO = os.path.join(REPO, "research", "ea_predictions_zero.csv")

COMPS = ["gk_stop","sp_threat","sp_vuln","atk_fin","atk_create","atk_pen","def_win","ctrl","pace_trans"]
WC = {"WC2018","WC2022"}

def load_asof(path, keycol, datecol):
    d = defaultdict(list)
    for r in csv.DictReader(open(path, encoding="utf-8")):
        d[r[keycol]].append((r[datecol], r))
    for k in d: d[k].sort(key=lambda x: x[0])
    return d

def asof(d, team, when):
    best=None
    for dt, r in d.get(team, []):
        if dt <= when: best=r
        else: break
    return best

def fnum(s):
    try: return float(s)
    except (ValueError, TypeError): return None

def corr(xs, ys):
    if len(xs) < 3: return float("nan")
    x=np.asarray(xs,float); y=np.asarray(ys,float)
    if x.std()==0 or y.std()==0: return float("nan")
    return float(np.corrcoef(x,y)[0,1])

def main():
    ea = load_asof(EA, "team", "as_of")
    mv = load_asof(MV, "team", "as_of")
    matches = list(csv.DictReader(open(ZERO, encoding="utf-8")))
    tdate = {}
    for m in matches:
        t=m["tournament"]; tdate[t]=min(m["date"], tdate.get(t, m["date"]))

    rec = {}
    for m in matches:
        for side in ("home","away"):
            team=m[side]; t=m["tournament"]; when=tdate[t]
            if (t,team) in rec: continue
            er=asof(ea, team, when); vr=asof(mv, team, when)
            if er is None or vr is None: continue
            ov=fnum(er["ovr_top26"]); val=fnum(vr["value_eur"])
            if ov is None or val is None or val<=0: continue
            rec[(t,team)] = {"ovr":ov, "logv":float(np.log(val)),
                             "comps":{c: fnum(er[c]) for c in COMPS}}

    tours=sorted({t for (t,_) in rec})
    resid={c:{} for c in COMPS}
    for c in COMPS:
        for T in tours:
            tr=[v for k,v in rec.items() if k[0]!=T and v["comps"][c] is not None]
            te=[(k,v) for k,v in rec.items() if k[0]==T and v["comps"][c] is not None]
            if len(tr)<20 or not te: continue
            C=np.array([v["comps"][c] for v in tr]); O=np.array([v["ovr"] for v in tr]); L=np.array([v["logv"] for v in tr])
            cm,cs=C.mean(),C.std(); om,osd=O.mean(),O.std(); lm,ls=L.mean(),L.std()
            if cs==0 or osd==0 or ls==0: continue
            X=np.column_stack([np.ones(len(tr)),(O-om)/osd,(L-lm)/ls])
            beta,_,_,_=np.linalg.lstsq(X,(C-cm)/cs,rcond=None)
            for k,v in te:
                oz=(v["ovr"]-om)/osd; lz=(v["logv"]-lm)/ls; cz=(v["comps"][c]-cm)/cs
                resid[c][k]=cz-(beta[0]+beta[1]*oz+beta[2]*lz)

    def outres(m):
        y=1.0 if m["actual"]=="home" else 0.5 if m["actual"]=="draw" else 0.0
        return y-(float(m["p_home"])+0.5*float(m["p_draw"]))
    def feat_single(c,m):
        h=resid[c].get((m["tournament"],m["home"])); a=resid[c].get((m["tournament"],m["away"]))
        return None if h is None or a is None else h-a
    def feat_pair(m):
        out=[]
        for k in ((m["tournament"],m["home"]),(m["tournament"],m["away"])):
            rt=resid["sp_threat"].get(k); rv=resid["sp_vuln"].get(k)
            if rt is None or rv is None: return None
            out.append(rt+rv)
        return out[0]-out[1]

    def evaluate(featfn):
        data=[(m["tournament"], featfn(m), outres(m)) for m in matches if featfn(m) is not None]
        pooled=corr([d[1] for d in data],[d[2] for d in data])
        wc=[d for d in data if d[0] in WC]; co=[d for d in data if d[0] not in WC]
        cwc=corr([d[1] for d in wc],[d[2] for d in wc]); cco=corr([d[1] for d in co],[d[2] for d in co])
        pos=neg=0
        for T in tours:
            sub=[d for d in data if d[0]==T]
            cb=corr([d[1] for d in sub],[d[2] for d in sub])
            if cb==cb:
                pos+=cb>0; neg+=cb<0
        return pooled,cwc,cco,len(data),pos,neg
    def anchor_panel(c):
        ks=[k for k in rec if rec[k]["comps"][c] is not None]
        C=np.array([rec[k]["comps"][c] for k in ks]); O=np.array([rec[k]["ovr"] for k in ks]); L=np.array([rec[k]["logv"] for k in ks])
        Cz=(C-C.mean())/C.std(); Oz=(O-O.mean())/O.std(); Lz=(L-L.mean())/L.std()
        X=np.column_stack([np.ones(len(ks)),Oz,Lz]); beta,_,_,_=np.linalg.lstsq(X,Cz,rcond=None)
        r2=1-((Cz-X@beta)**2).sum()/((Cz-Cz.mean())**2).sum()
        return corr(C,O),corr(C,L),r2

    print(f"=== EA sub-attribute kill test: {len(rec)} team-editions, {len(tours)} blocks ===")
    nwc=sum(1 for m in matches if m['tournament'] in WC)
    print(f"    surface: {len(matches)} matches ({nwc} WC, {len(matches)-nwc} continental)\n")
    print(f"{'composite':<11}{'pooled':>8}{'WC':>8}{'cont':>8}{'n':>6}{'blk+/-':>8}   {'cVAL':>6}{'cOVR':>6}{'jR2':>6}{'left':>6}")
    results={}
    for c in COMPS:
        p,w,co,n,pos,neg=evaluate(lambda m,c=c: feat_single(c,m))
        cO,cL,r2=anchor_panel(c)
        print(f"{c:<11}{p:+8.3f}{w:+8.3f}{co:+8.3f}{n:6d}{str(pos)+'/'+str(neg):>8}   {cL:+6.2f}{cO:+6.2f}{r2:6.2f}{1-r2:6.2f}")
        results[c]=(p,w,co)
    p,w,co,n,pos,neg=evaluate(feat_pair)
    print(f"{'sp_pair':<11}{p:+8.3f}{w:+8.3f}{co:+8.3f}{n:6d}{str(pos)+'/'+str(neg):>8}   (coupled threat+vuln, the gated form)")
    results["sp_pair"]=(p,w,co)

    def verdict(p,w,co):
        if p>=0.07 and w>0 and co>0: return "PASS (build pipeline)"
        if p<=0.03 or (w*co<0): return "KILL (no pipeline)"
        return "NEAR ZONE (no build; exploratory positive)"
    print("\n=== decision point 1 (frozen thresholds; authority only for gk_stop and the set-piece pair) ===")
    for name in ("gk_stop","sp_pair"):
        p,w,co=results[name]
        print(f"  {name:<8} pooled={p:+.3f}  WC={w:+.3f}  cont={co:+.3f}   ->  {verdict(p,w,co)}")
    print("  null SE of a pooled correlation at n=768 is about 0.036; +0.07 is ~two SE.")
    print("  (the seven probe/individual rows above are prioritization only, no gate authority.)")

main()
