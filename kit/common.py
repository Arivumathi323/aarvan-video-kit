"""Shared helpers: brand, fonts, easing, sprites, compositing, grade."""
import json, os, subprocess, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = json.load(open(os.path.join(ROOT, 'brand', 'brand.json')))
C = {k: tuple(v) for k, v in BRAND['colors'].items()}
ACCENT, DARK, WHITE, GREY, STROKE = C['accent'], C['dark'], C['white'], C['grey'], C['stroke']


def fpath(kind):
    return os.path.join(ROOT, 'fonts', BRAND['fonts'][kind])


_fc = {}
def font(kind, size):
    k = (kind, int(size))
    if k not in _fc: _fc[k] = ImageFont.truetype(fpath(kind), int(size))
    return _fc[k]


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_io(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def back_out(x, s=1.9):
    x = clamp(x) - 1; return x * x * ((s + 1) * x + s) + 1


# ---------- probing ----------
def probe(path):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', path],
                                  capture_output=True, check=True).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    num, den = v.get('avg_frame_rate', '30/1').split('/')
    fps = float(num) / float(den) if float(den) else 30.0
    w, h = int(v['width']), int(v['height'])
    rot = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd: rot = int(sd['rotation'])
    rot = int(v.get('tags', {}).get('rotate', rot) or rot)
    if abs(rot) % 180 == 90: w, h = h, w
    has_audio = any(s['codec_type'] == 'audio' for s in j['streams'])
    return dict(w=w, h=h, fps=fps, dur=float(j['format']['duration']), audio=has_audio)


# ---------- sprites (RGBA numpy) ----------
def text_sprite(text, kind, size, fill=WHITE, stroke=0, stroke_fill=STROKE, shadow=True, pad=None):
    f = font(kind, size); pad = pad if pad is not None else int(size * 0.4)
    bb = f.getbbox(text, stroke_width=stroke)
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - bb[0] + size * .04, pad - bb[1] + size * .08), text, font=f, fill=(0, 0, 0, 150),
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(max(2, size * .1))))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return np.array(im)


def pill_sprite(text, kind, size, bg, fg, radius=None, border=None):
    f = font(kind, size); bb = f.getbbox(text)
    padx, pady = int(size * .85), int(size * .45)
    w, h = bb[2] - bb[0] + padx * 2, bb[3] - bb[1] + pady * 2
    m = int(size * .7)
    im = Image.new('RGBA', (w + m * 2, h + m * 2), (0, 0, 0, 0))
    r = radius if radius is not None else h // 2
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((m + 2, m + size * .2, m + w + 2, m + h + size * .2), r, fill=(0, 0, 0, 140))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(size * .25)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((m, m, m + w, m + h), r, fill=bg, outline=border, width=max(2, int(size * .1)) if border else 0)
    d.text((m + padx - bb[0], m + pady - bb[1]), text, font=f, fill=fg)
    return np.array(im)


def blit(frame, spr, cx, cy, scale=1.0, alpha=1.0, anchor='c', mask_below=None):
    """Alpha-composite an RGBA sprite onto a float32 RGB frame.
    mask_below: optional float mask (H,W) in 0..1 — where it is 1 the sprite is hidden (draws behind the person)."""
    if alpha <= 0.003 or scale <= 0.01: return
    s = spr
    if abs(scale - 1) > 1e-3:
        s = cv2.resize(spr, (max(1, int(spr.shape[1] * scale)), max(1, int(spr.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
    H, W = frame.shape[:2]; h, w = s.shape[:2]
    if anchor == 'c': x0, y0 = int(cx - w / 2), int(cy - h / 2)
    elif anchor == 'l': x0, y0 = int(cx), int(cy - h / 2)
    else: x0, y0 = int(cx - w), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb: return
    sub = s[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32)
    a = sub[..., 3:4] / 255.0 * alpha
    if mask_below is not None: a = a * (1 - mask_below[ya:yb, xa:xb, None])
    dst = frame[ya:yb, xa:xb]
    dst[:] = dst * (1 - a) + sub[..., :3] * a


# ---------- look ----------
_vig = {}
def vignette(W, H, amt=0.2):
    k = (W, H, amt)
    if k not in _vig:
        vy, vx = np.ogrid[:H, :W]
        _vig[k] = (1 - amt * (((vx - W / 2) / (W / 2)) ** 2 + ((vy - H / 2) / (H / 2)) ** 2) ** 1.4).clip(0.55, 1)[..., None].astype(np.float32)
    return _vig[k]


def grade(img, look='aarvan', sharpen=0.6):
    x = img.astype(np.float32) / 255.0
    if look != 'none':
        x = x * np.array([0.98, 0.985, 1.05], np.float32)
        lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
        x = lum[..., None] + (x - lum[..., None]) * 1.18
        x = (x - 0.5) * 1.12 + 0.5 - 0.02
        x = np.clip(x, 0, 1) ** 1.05
    x = x * 255.0
    if sharpen > 0:
        x = cv2.addWeighted(x, 1 + sharpen, cv2.GaussianBlur(x, (0, 0), 2.2), -sharpen, 0)
    return x * vignette(img.shape[1], img.shape[0])


def diag_band(frame, prog, alpha=1.0, u=1.0):
    """Brand element: orange diagonal band in the top-right corner."""
    if prog <= 0: return
    H, W = frame.shape[:2]
    ov = np.zeros((H, W), np.uint8)
    off = int((1 - ease_out(prog)) * 500 * u)
    a1, a2 = int(330 * u), int(170 * u)
    pts = np.array([[W - a1 + off, 0], [W - a2 + off, 0], [W + off, a2], [W + off, a1]], np.int32)
    cv2.fillPoly(ov, [pts], 255, lineType=cv2.LINE_AA)
    a = ov[..., None].astype(np.float32) / 255 * alpha
    frame[:] = frame * (1 - a) + np.array(ACCENT, np.float32) * a
