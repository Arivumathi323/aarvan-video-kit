"""Render an Aarvan Hologram HUD insert (code-drawn wireframe + HUD, ice-blue lines, Aarvan orange only on locked values).
usage: python hud.py --new <project_dir>                                   copy the template (brand/hud) to start from
       python hud.py <project_dir> <out.mp4> [--insert 1|2] [--size 1080x1920] [--fps 24]

The page follows the Lemo-Opuscar page contract (window.render(t), DUR, READY) and is rendered frame by frame with
Lemo-Opuscar's MIT render tools (core/render/video.mjs). The library is cloned to ~/lemo-opuscar on first use
(or set LEMO_OPUSCAR_HOME). Its style prompts are not copied into this repo.

Template inserts (edit main.js to make your own):
  --insert 1  automation hub: MSG / MAIL / FORM ports, the AI core opens, a card locks DONE      (1080x1920, 3.25 s)
  --insert 2  phone feed: AARVAN LABS title, chips AI AGENTS / AI UPDATES / AI NEWS, DAILY      (1080x1920 or 1080x1080, 5.2 s)
Place the result with an `inserts` entry in an edit plan: {"clip": "hud1.mp4", "at": {"word": "..."}, "mode": "full"}.
"""
import os, sys, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

LEMO_REPO = 'https://github.com/lemomo-ai/lemo-opuscar.git'


def lemo():
    lib = os.environ.get('LEMO_OPUSCAR_HOME', os.path.expanduser('~/lemo-opuscar'))
    if not os.path.exists(os.path.join(lib, 'core', 'render', 'video.mjs')):
        print('Getting the Lemo-Opuscar render tools (one time)...', flush=True)
        subprocess.run(['git', 'clone', '-q', '--depth', '1', LEMO_REPO, lib], check=True)
    if not os.path.exists(os.path.join(lib, 'node_modules')):
        print('Installing its render packages (one time, a few minutes)...', flush=True)
        subprocess.run(['sh', os.path.join(lib, 'plugin', 'skills', 'lemo-opuscar', 'scripts', 'setup.sh'), 'deps'], check=True, cwd=lib)
    return lib


def main(a):
    if not a or a[0] in ('-h', '--help'): print(__doc__); return 1
    if a[0] == '--new':
        dst = os.path.abspath(a[1]); shutil.copytree(os.path.join(ROOT, 'brand', 'hud'), dst, dirs_exist_ok=True)
        print('Template copied to', dst, '- edit main.js (labels, timings) then: aarvan hud', a[1], 'out.mp4 --insert 1'); return 0
    proj, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    opt = dict(zip(a[2::2], a[3::2])); n = opt.get('--insert', '1'); size = opt.get('--size', '1080x1920'); fps = opt.get('--fps', '24')
    if not os.path.exists(os.path.join(proj, 'models', 'hub.json')):
        subprocess.run(['node', 'gen_models.mjs'], cwd=os.path.join(proj, 'models'), check=True)
    lib = lemo()
    subprocess.run(['node', 'core/render/video.mjs', proj, '--fps', fps, '--workers', '2', '--size', size, '--q', f'insert={n}', '--out', out], cwd=lib, check=True)
    print('Done:', out); return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
