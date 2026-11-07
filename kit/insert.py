"""Render a HyperFrames (HTML + GSAP) project into an MP4 insert for an edit.
usage: python insert.py <project_dir> <out.mp4>
       python insert.py --new flow <project_dir>     copy a brand template (brand/hyperframes/<name>) to start from

HyperFrames (HeyGen, Apache 2.0) renders HTML to video with Chrome. Telemetry is switched off here.
Write compositions with the hyperframes skills/docs: https://hyperframes.heygen.com
"""
import os, sys, shutil, subprocess, glob, tarfile, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

HF = 'hyperframes@0.9.19'
GSAP = 'gsap@3.15.0'


def chrome():
    for p in [os.environ.get('HYPERFRAMES_BROWSER_PATH'), shutil.which('google-chrome'), shutil.which('chromium'),
              shutil.which('chromium-browser'), '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']:
        if p and os.path.exists(p): return p
    hits = sorted(glob.glob(os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome')))
    return hits[-1] if hits else None


def prepare(proj):
    """Local copies of GSAP and the brand fonts, so renders never depend on a CDN."""
    if not os.path.exists(os.path.join(proj, 'gsap.min.js')):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(['npm', 'pack', '-s', GSAP], cwd=d, check=True, capture_output=True)
            tgz = glob.glob(os.path.join(d, '*.tgz'))[0]
            with tarfile.open(tgz) as t:
                m = t.getmember('package/dist/gsap.min.js'); m.name = 'gsap.min.js'
                try: t.extract(m, proj, filter='data')
                except TypeError: t.extract(m, proj)
    for f in glob.glob(os.path.join(ROOT, 'fonts', '*.otf')) + glob.glob(os.path.join(ROOT, 'fonts', '*.ttf')):
        if not os.path.exists(os.path.join(proj, os.path.basename(f))): shutil.copy(f, proj)


def render(proj, out):
    prepare(proj)
    env = dict(os.environ, HYPERFRAMES_NO_TELEMETRY='1', DO_NOT_TRACK='1', HYPERFRAMES_SKIP_SKILLS='1')
    c = chrome()
    if c: env['HYPERFRAMES_BROWSER_PATH'] = c
    out = os.path.abspath(out)
    r = subprocess.run(['npx', '-y', HF, 'render', '--output', out], cwd=proj, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print(r.stdout[-1500:], r.stderr[-1500:]); raise SystemExit('HyperFrames render failed (run: npx hyperframes doctor)')
    print('Rendered', out)


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == '--new':
        src = os.path.join(ROOT, 'brand', 'hyperframes', sys.argv[2]); shutil.copytree(src, sys.argv[3]); print('Template copied to', sys.argv[3])
    elif len(sys.argv) == 3:
        render(sys.argv[1], sys.argv[2])
    else:
        print(__doc__); sys.exit(1)
