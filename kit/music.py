"""Original music + sound effects, synthesised (no licensing issues).
usage: python music.py <seconds> <out_dir> [--bpm 116] [--mood punchy|chill|cinematic]"""
import sys, argparse, os
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, sosfilt_zi


def make(DUR, outdir, bpm=116, mood='punchy', seed=7):
    os.makedirs(outdir, exist_ok=True)
    sr=44100; beat=60/bpm; bar=beat*4
    N=int(sr*DUR)+sr
    L=np.zeros(N); R=np.zeros(N); rng=np.random.default_rng(seed)
    def add(sig,t,gl=1,gr=1):
        i=int(t*sr); j=min(N,i+len(sig))
        if j<=i: return
        L[i:j]+=sig[:j-i]*gl; R[i:j]+=sig[:j-i]*gr
    def lp(x,f,o=2): return sosfilt(butter(o,f,'low',fs=sr,output='sos'),x)
    def hp(x,f,o=2): return sosfilt(butter(o,f,'high',fs=sr,output='sos'),x)
    def bp(x,a,b): return sosfilt(butter(2,[a,b],'band',fs=sr,output='sos'),x)
    def env(n,a,d): t=np.arange(n)/sr; return np.minimum(1,t/max(a,1e-4))*np.exp(-t/d)
    def saw(f,n,ph=0): t=np.arange(n)/sr; return 2*((t*f+ph)%1)-1
    def kick():
        n=int(.45*sr); t=np.arange(n)/sr; f=50+110*np.exp(-t*28)
        s=np.sin(2*np.pi*np.cumsum(f)/sr)*np.exp(-t*7)
        s[:200]+=rng.standard_normal(200)*.3*np.linspace(1,0,200); return np.tanh(s*1.6)*.9
    def clap():
        n=int(.25*sr); s=np.zeros(n); no=bp(rng.standard_normal(n),900,4000)
        for k,o in enumerate([0,.011,.022]):
            i=int(o*sr); e=env(n-i,.001,.012 if k<2 else .09); s[i:]+=no[i:]*e
        return s*.6
    def hat(d=.035): n=int(.2*sr); return hp(rng.standard_normal(n),7000)*env(n,.001,d)*.22
    midi=lambda m:440*2**((m-69)/12)
    prog=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]]  # Am F C G
    bass=[45,41,36,43]
    K,C,Hh,Ho=kick(),clap(),hat(),hat(.12)
    nb=int(DUR/bar)+1
    # sidechain envelope
    sc=np.ones(N)
    for b in range(nb):
        for q in range(4):
            t=b*bar+q*beat; i=int(t*sr); n=int(.3*sr); j=min(N,i+n)
            if b>=1: sc[i:j]=np.minimum(sc[i:j],0.35+0.65*(np.arange(j-i)/n)**.6)
    padL=np.zeros(N); padR=np.zeros(N); bs=np.zeros(N); arp=np.zeros(N)
    for b in range(nb):
        ch=prog[b%4]; t0=b*bar; i=int(t0*sr); n=int(bar*sr); j=min(N,i+n); m=j-i
        for note in ch:
            f=midi(note+12)
            for d,g in [(-0.12,.6),(0.0,1),(0.11,.6)]:
                ff=f*2**(d/12); padL[i:j]+=saw(ff,m,rng.random())*g*.05; padR[i:j]+=saw(ff*1.002,m,rng.random())*g*.05
        # bass 8ths
        for e in range(8):
            if b==0: break
            tt=t0+e*beat/2; ii=int(tt*sr); nn=int(beat/2*.9*sr); jj=min(N,ii+nn)
            if jj-ii<10: continue
            bs[ii:jj]+=lp(saw(midi(bass[b%4]),jj-ii),500)*env(jj-ii,.003,.18)*.5
        # arp 16ths
        seq=[0,1,2,1,2,0,1,2]
        for s16 in range(16):
            tt=t0+s16*beat/4; ii=int(tt*sr); nn=int(.16*sr); jj=min(N,ii+nn)
            if jj-ii<10: continue
            f=midi(ch[seq[s16%8]]+24); x=np.sign(np.sin(2*np.pi*f*np.arange(jj-ii)/sr))*.5+np.sin(2*np.pi*f*np.arange(jj-ii)/sr)*.5
            arp[ii:jj]+=lp(x,3500)*env(jj-ii,.002,.05)*(.07 if b>=1 else .04)
    padL=lp(padL,1800); padR=lp(padR,1800)
    # intro filter sweep on pad (bar 0)
    L+=padL*sc; R+=padR*sc; L+=bs*sc; R+=bs*sc
    # arp ping-pong
    d=int(beat*.75*sr); arpd=np.zeros(N); arpd[d:]=arp[:-d]*.45
    L+=arp+arpd*.3; R+=arp*.8+arpd
    for b in range(nb):
        t0=b*bar
        if b>=1:
            for q in range(4):
                if mood!='cinematic' or q==0: add(K,t0+q*beat)
            if mood=='punchy':
                for q in [1,3]: add(C,t0+q*beat,.9,1)
        for e in range(8):
            tt=t0+e*beat/2
            if e%2==1 and b>=1 and mood=='punchy': add(Ho,tt,.7,1)
            elif b>=1 or e>=4:
                if mood!='cinematic' or b>=4: add(Hh,tt,1,.7)
    # riser into bar 1
    n=int(bar*sr); t=np.arange(n)/sr; rs=hp(rng.standard_normal(n),3000)*(t/bar)**2*.25; add(rs,0)
    mix=np.stack([L,R],1)[:int(DUR*sr)]
    # fade out last 1.5s
    f=int(1.5*sr); mix[-f:]*=np.linspace(1,0,f)[:,None]
    mix=np.tanh(mix*1.3)/1.3; mix/=np.abs(mix).max()/0.9
    sf.write(os.path.join(outdir,'music.wav'),mix,sr)
    # --- SFX ---
    def whoosh(d=.55,rev=False):
        n=int(d*sr); x=rng.standard_normal(n); out=np.zeros(n); blk=256; zi=None
        for k in range(0,n,blk):
            p=k/n; fc=300+5000*(np.sin(np.pi*p))**1.5
            sos=butter(2,[fc*.6,min(fc*1.6,20000)],'band',fs=sr,output='sos')
            if zi is None: zi=sosfilt_zi(sos)*0
            out[k:k+blk],zi=sosfilt(sos,x[k:k+blk],zi=zi)
        e=np.sin(np.pi*np.linspace(0,1,n))**2; out*=e; out/=np.abs(out).max(); return out*.8
    w=whoosh(); sf.write(os.path.join(outdir,'whoosh.wav'),np.stack([w*np.linspace(1.2,.6,len(w)),w*np.linspace(.6,1.2,len(w))],1)*.8,sr)
    n=int(.09*sr); t=np.arange(n)/sr; pop=np.sin(2*np.pi*(600*t+3000*t**2))*np.exp(-t*45); sf.write(os.path.join(outdir,'pop.wav'),pop*.7,sr)
    n=int(1.2*sr); t=np.arange(n)/sr; imp=np.sin(2*np.pi*np.cumsum(40+80*np.exp(-t*12))/sr)*np.exp(-t*3.5)+lp(rng.standard_normal(n),900)*np.exp(-t*6)*.5
    sf.write(os.path.join(outdir,'impact.wav'),np.tanh(imp*1.5)*.8,sr)
    # signature drop sound: rising swoosh into a deep boom
    n1=int(.5*sr); t=np.arange(n1)/sr; rise=whoosh(.5)*np.linspace(.2,1,n1)**2
    n2=int(1.4*sr); t2=np.arange(n2)/sr
    boom=np.sin(2*np.pi*np.cumsum(38+120*np.exp(-t2*16))/sr)*np.exp(-t2*2.6)+lp(rng.standard_normal(n2),1200)*np.exp(-t2*9)*.6
    drop=np.concatenate([rise*.7,np.tanh(boom*1.8)*.9]); sf.write(os.path.join(outdir,'drop.wav'),np.stack([drop,drop],1)*.85,sr)
    return os.path.join(outdir,'music.wav')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('seconds', type=float); ap.add_argument('out_dir')
    ap.add_argument('--bpm', type=int, default=116); ap.add_argument('--mood', default='punchy')
    a = ap.parse_args(); print(make(a.seconds, a.out_dir, a.bpm, a.mood))
