import sys, math, csv
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from scipy.special import gammaln

MAXG = 10

class Match:
    __slots__ = ("date","home","away","hg","ag","tournament","neutral")
    def __init__(self, date, home, away, hg, ag, tournament, neutral):
        self.date=date; self.home=home; self.away=away
        self.hg=hg; self.ag=ag; self.tournament=tournament; self.neutral=neutral

def load(path):
    rows=[]
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            try: hg=int(r["home_score"]); ag=int(r["away_score"])
            except (ValueError, KeyError): continue
            y,m,d=map(int, r["date"].split("-"))
            rows.append(Match(y*372+m*31+d, r["home_team"], r["away_team"], hg, ag,
                     r["tournament"], r["neutral"].strip().lower()=="true"))
    rows.sort(key=lambda x:x.date); return rows

def _wdl(M):
    M=M/M.sum()
    return float(np.tril(M,-1).sum()), float(np.trace(M)), float(np.triu(M,1).sum())

def wdl_independent(lh,la):
    return _wdl(np.outer(poisson.pmf(np.arange(MAXG+1),lh), poisson.pmf(np.arange(MAXG+1),la)))

def wdl_dixoncoles(lh,la,rho):
    M=np.outer(poisson.pmf(np.arange(MAXG+1),lh), poisson.pmf(np.arange(MAXG+1),la))
    M[0,0]*=1-lh*la*rho; M[0,1]*=1+lh*rho; M[1,0]*=1+la*rho; M[1,1]*=1-rho
    return _wdl(np.clip(M,0,None))

def wdl_bivariate(lh,la,l3):
    l1=max(lh-l3,1e-9); l2=max(la-l3,1e-9)
    f=[math.factorial(k) for k in range(MAXG+1)]; base=math.exp(-(l1+l2+l3))
    M=np.zeros((MAXG+1,MAXG+1))
    for x in range(MAXG+1):
        for y in range(MAXG+1):
            s=0.0
            for k in range(min(x,y)+1):
                s+=(l1**(x-k)/f[x-k])*(l2**(y-k)/f[y-k])*(l3**k/f[k])
            M[x,y]=base*s
    return _wdl(M)

class DixonColes:
    def __init__(self, half_life_years=2.0, l2=0.02, bivariate=False):
        self.xi=math.log(2)/(half_life_years*372); self.l2=l2; self.bivariate=bivariate
    def fit(self, matches, asof):
        teams=sorted({m.home for m in matches}|{m.away for m in matches})
        self.idx={t:i for i,t in enumerate(teams)}; n=len(teams); self.teams=teams
        H=np.array([self.idx[m.home] for m in matches]); A=np.array([self.idx[m.away] for m in matches])
        hg=np.array([m.hg for m in matches],float); ag=np.array([m.ag for m in matches],float)
        neu=np.array([0.0 if m.neutral else 1.0 for m in matches])
        w=np.exp(-self.xi*(asof-np.array([m.date for m in matches],float)))
        lhg=gammaln(hg+1); lag=gammaln(ag+1)
        biv=self.bivariate
        def negll(p):
            mu=p[0]; att=p[1:1+n]-p[1:1+n].mean(); dfn=p[1+n:1+2*n]-p[1+n:1+2*n].mean()
            gamma=p[1+2*n]; rho=np.clip(p[2+2*n],-0.18,0.18)
            lh=np.exp(mu+att[H]+dfn[A]+gamma*neu); la=np.exp(mu+att[A]+dfn[H])
            ll=w*(hg*np.log(lh)-lh-lhg + ag*np.log(la)-la-lag)
            if not biv:
                tau=np.ones_like(lh)
                m00=(hg==0)&(ag==0); m01=(hg==0)&(ag==1); m10=(hg==1)&(ag==0); m11=(hg==1)&(ag==1)
                tau[m00]=np.clip(1-lh[m00]*la[m00]*rho,1e-6,None); tau[m01]=1+lh[m01]*rho
                tau[m10]=1+la[m10]*rho; tau[m11]=1-rho
                ll=ll+w*np.log(np.clip(tau,1e-6,None))
            return -(ll.sum())+self.l2*(att@att+dfn@dfn)
        p0=np.zeros(3+2*n); p0[0]=math.log(1.3); p0[2+2*n]=0.0; p0[1+2*n]=0.25
        res=minimize(negll,p0,method="L-BFGS-B",options=dict(maxiter=500))
        p=res.x
        self.mu=p[0]; self.att=p[1:1+n]-p[1:1+n].mean(); self.dfn=p[1+n:1+2*n]-p[1+n:1+2*n].mean()
        self.gamma=p[1+2*n]; self.rho=float(np.clip(p[2+2*n],-0.18,0.18))
        if biv:
            # fixed covariance term (constant 0.10; not fitted)
            self.l3=0.10
        return self
    def _rates(self,home,away,neutral):
        a=self.att[self.idx[home]] if home in self.idx else 0.0
        da=self.dfn[self.idx[away]] if away in self.idx else 0.0
        aa=self.att[self.idx[away]] if away in self.idx else 0.0
        dh=self.dfn[self.idx[home]] if home in self.idx else 0.0
        g=0.0 if neutral else self.gamma
        return math.exp(self.mu+a+da+g), math.exp(self.mu+aa+dh)
    def wdl(self,home,away,neutral):
        lh,la=self._rates(home,away,neutral)
        if self.bivariate:
            return wdl_bivariate(lh,la,min(self.l3,0.9*min(lh,la)))
        return wdl_dixoncoles(lh,la,self.rho)

def running_gaps(matches,home_adv=50.0):
    R=defaultdict(lambda:1500.0); gaps=[]
    for m in matches:
        rh=R[m.home]; ra=R[m.away]; eff=rh+(0 if m.neutral else home_adv)
        gaps.append(eff-ra)
        E=1/(1+10**((ra-eff)/400)); t=m.tournament.lower()
        k=60 if t=="fifa world cup" else 40 if "qualification" in t else 30 if "friendly" in t else 35
        md=abs(m.hg-m.ag); k*=1.0 if md<=1 else 1.5 if md==2 else 1.75+(md-3)/8.0
        actual=1.0 if m.hg>m.ag else 0.5 if m.hg==m.ag else 0.0
        d=k*(actual-E); R[m.home]=rh+d; R[m.away]=ra-d
    return gaps,R,home_adv

class EloPoisson:
    def fit(self,matches):
        gaps,R,ha=running_gaps(matches); s=np.array(gaps)/100.0
        hg=np.array([m.hg for m in matches],float); ag=np.array([m.ag for m in matches],float)
        def negll(p):
            c0,c1,c2=p; lh=np.exp(c0+c1*s); la=np.exp(c0-c2*s)
            return -np.sum(hg*np.log(lh)-lh + ag*np.log(la)-la)
        self.c0,self.c1,self.c2=minimize(negll,[math.log(1.3),0.3,0.3],method="L-BFGS-B").x
        self.R=R; self.home_adv=ha; return self
    def wdl(self,home,away,neutral):
        rh=self.R.get(home,1500.0); ra=self.R.get(away,1500.0)
        s=((rh+(0 if neutral else self.home_adv))-ra)/100.0
        return wdl_independent(math.exp(self.c0+self.c1*s), math.exp(self.c0-self.c2*s))

DRAW_RATE=[0.299,0.289,0.270,0.252,0.243,0.200,0.181,0.150,0.125,0.102,0.076,0.041,0.022]
def draw_prob(gap):
    g=abs(gap); m=(len(DRAW_RATE)-1)*50.0
    if g>=m: return DRAW_RATE[-1]
    b=int(g/50.0); t=(g-b*50.0)/50.0
    return DRAW_RATE[b]*(1-t)+DRAW_RATE[b+1]*t
class EloDrawBaseline:
    def fit(self,matches):
        _,R,ha=running_gaps(matches); self.R=R; self.home_adv=ha; return self
    def wdl(self,home,away,neutral):
        rh=self.R.get(home,1500.0); ra=self.R.get(away,1500.0)
        eff=rh+(0 if neutral else self.home_adv); gap=eff-ra
        E=1/(1+10**((ra-eff)/400)); pd=draw_prob(gap); pw=max(0.0,min(1-pd,E-pd/2))
        return pw,pd,1-pd-pw

def mcb(p,a): e=[0,0,0]; e[a]=1; return sum((p[i]-e[i])**2 for i in range(3))
def outcome(m): return 0 if m.hg>m.ag else 1 if m.hg==m.ag else 2

def synthetic_test():
    rng=np.random.default_rng(7); n=24; teams=[f"T{i:02d}" for i in range(n)]
    att=rng.normal(0,0.35,n); att-=att.mean(); dfn=rng.normal(0,0.30,n); dfn-=dfn.mean()
    mu=math.log(1.35); gamma=0.30
    def gen(date):
        i,j=rng.choice(n,2,replace=False); neutral=rng.random()<0.3
        lh=math.exp(mu+att[i]+dfn[j]+(0 if neutral else gamma)); la=math.exp(mu+att[j]+dfn[i])
        return Match(date,teams[i],teams[j],int(rng.poisson(lh)),int(rng.poisson(la)),"Friendly",neutral)
    data=[gen(300000+d) for d in range(6000)]; train=data[:5000]; test=data[5000:]
    dc=DixonColes(half_life_years=80).fit(train, asof=400000)
    estd=np.array([dc.att[dc.idx[t]] for t in teams]); corr=np.corrcoef(att,estd)[0,1]
    def score(model):
        bs=[]; hit=0
        for m in test:
            p=model.wdl(m.home,m.away,m.neutral); a=outcome(m)
            bs.append(mcb(p,a)); hit+=(max(range(3),key=lambda i:p[i])==a)
        return hit/len(test), sum(bs)/len(bs)
    biv=DixonColes(half_life_years=80,bivariate=True).fit(train,asof=400000)
    base=EloDrawBaseline().fit(train); elo=EloPoisson().fit(train)
    print("=== SYNTHETIC SELF-TEST (data generated from a Dixon-Coles process) ===")
    print(f"attack-strength recovery corr(true,est) = {corr:.3f}  (want > 0.9)")
    print(f"{'model':16s} {'pick-acc':>9s} {'Brier':>7s}")
    for name,mdl in [("Dixon-Coles",dc),("Bivariate",biv),("Elo-Poisson",elo),("Elo+DrawModel",base)]:
        a,b=score(mdl); print(f"{name:16s} {a*100:8.1f}% {b:7.3f}")
    print("uniform-guess reference Brier = 0.667")
    p=dc.wdl(teams[0],teams[1],False); print("normalisation check sum=%.9f"%sum(p)); assert abs(sum(p)-1)<1e-9

def real_test(path):
    data=load(path); print(f"loaded {len(data):,} matches {data[0].date} .. {data[-1].date}")
    WC={f"WC{y}":(y*372+5*31+20, y*372+7*31+20) for y in (2006,2010,2014,2018,2022)}
    def run(fac):
        H=N=0; bn=0.0
        for label,(s,e) in WC.items():
            train=[m for m in data if m.date<s and m.date>=s-12*372]
            test=[m for m in data if s<=m.date<e and m.tournament.lower()=="fifa world cup"]
            if not test: continue
            mdl=fac()
            mdl.fit(train, asof=s) if isinstance(mdl,DixonColes) else mdl.fit(train)
            for m in test:
                p=mdl.wdl(m.home,m.away,m.neutral); a=outcome(m)
                bn+=mcb(p,a); N+=1; H+=(max(range(3),key=lambda i:p[i])==a)
        return H,N,bn/max(N,1)
    for name,fac in [("Dixon-Coles",lambda:DixonColes()),("Bivariate",lambda:DixonColes(bivariate=True)),
                     ("Elo-Poisson",EloPoisson),("Elo+DrawModel",EloDrawBaseline)]:
        H,N,b=run(fac); print(f"{name:16s} {H}/{N} ({100*H/N:.1f}%)  multiclass Brier {b:.3f}")

if __name__=="__main__":
    if len(sys.argv)>1: real_test(sys.argv[1])
    else: synthetic_test()
