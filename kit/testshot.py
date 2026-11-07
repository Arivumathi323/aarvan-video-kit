"""Check a short test recording BEFORE filming the real video: framing, headroom, light, sound, steadiness.
usage: python testshot.py test.mp4 [--for reels|youtube|assignment]

Each line says what's fine and exactly what to change. A 5-10 second clip of you talking is enough.
"""
import argparse, os, sys, subprocess
import numpy as np, cv2
try: cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception: pass, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import probe
from track import read_frames, MODELS


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('clip'); ap.add_argument('--for', dest='target', default='reels')
    a = ap.parse_args(); info = probe(a.clip); rows = []
    add = lambda lv, name, msg: rows.append((lv, name, msg))
    vert = info['h'] > info['w']; short = min(info['w'], info['h'])

    # ---- format
    want_vert = a.target in ('reels', 'shorts')
    if want_vert != vert:
        add('FIX', 'orientation', f"{'landscape' if not vert else 'vertical'} clip for {a.target}: turn the phone "
            f"{'upright (vertical)' if want_vert else 'sideways (landscape)'}")
    else:
        add('OK', 'orientation', 'vertical' if vert else 'landscape')
    add('OK' if short >= 1080 else 'FIX', 'resolution', f"{info['w']}x{info['h']}" + ('' if short >= 1080 else
        ': set the camera to 1080p or 4K (webcams at 720p look soft once zoomed)'))
    add('OK' if info['fps'] >= 24 else 'FIX', 'frame rate', f"{info['fps']:.0f} fps" + ('' if info['fps'] >= 24 else ': use 30 fps'))

    # ---- picture: face, headroom, light, steadiness
    W = 360; H = int(round(W * info['h'] / info['w'])); H -= H % 2
    fd = cv2.FaceDetectorYN.create(os.path.join(MODELS, 'yunet.onnx'), '', (W, H), 0.6, 0.3, 20)
    faces, lum_face, lum_bg, clip_hi, shifts = [], [], [], [], []
    prev = None
    for i, fr in read_frames(a.clip, W, H, fps=5):
        bgr = cv2.cvtColor(fr, cv2.COLOR_RGB2BGR); g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY).astype(np.float32)
        _, f = fd.detect(bgr)
        if f is not None and len(f):
            x, y, w, h = max(f, key=lambda r: r[2] * r[3])[:4]
            faces.append((x / W, y / H, w / W, h / H))
            m = np.zeros(g.shape, bool); m[int(max(0, y)):int(y + h), int(max(0, x)):int(x + w)] = True
            lum_face.append(g[m].mean()); bgm = np.ones(g.shape, bool); bgm[int(max(0, y - h)):, int(max(0, x - w)):int(x + 2 * w)] = False
            if bgm.any(): lum_bg.append(g[bgm].mean())
        clip_hi.append((g > 250).mean())
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g); shifts.append(np.hypot(dx, dy))
        prev = g
    if not faces:
        add('FIX', 'face', 'no face found: face the camera, with light on your face')
    else:
        fx, fy, fw, fh = np.median(np.array(faces), 0)
        head_top = fy - 0.35 * fh            # hair line above the detected face box
        need = 0.12 if vert else 0.08
        if head_top < 0.03:
            add('FIX', 'headroom', 'your head touches the top of the frame: step back or tilt the camera down; '
                'the Aarvan Drop and labels need room above your head')
        elif head_top < need:
            add('WARN', 'headroom', f'tight ({head_top:.0%} above your head): a little more space makes room for the Drop word and labels')
        else:
            add('OK', 'headroom', f'{head_top:.0%} of the frame above your head')
        size = fw
        if size > (0.45 if vert else 0.28):
            add('WARN', 'distance', 'very close: sit or stand a bit further back (waist or chest up is ideal)')
        elif size < (0.14 if vert else 0.07):
            add('WARN', 'distance', 'far away: come closer, your face is small for phone screens')
        else:
            add('OK', 'distance', 'good size in frame')
        if abs(fx + fw / 2 - 0.5) > 0.2:
            add('WARN', 'centring', 'you are off to one side: centre yourself (or leave the empty side for graphics on purpose)')
        lf = float(np.median(lum_face)); lb = float(np.median(lum_bg)) if lum_bg else lf
        if lb - lf > 35:
            add('FIX', 'light', f'backlit: the background is much brighter than your face; face the window or lamp, never sit with it behind you')
        elif lf < 75:
            add('FIX', 'light', 'your face is dark: add light in front of you (window or lamp facing you)')
        elif lf > 205 or np.mean(clip_hi) > 0.06:
            add('WARN', 'light', 'overexposed: too bright; move back from the light or lower exposure (tap and drag down on the phone)')
        else:
            add('OK', 'light', f'face brightness {lf:.0f}/255, background {lb:.0f}')
    if shifts:
        sh = float(np.median(shifts)) * info['w'] / W
        add('OK' if sh < 3 else 'FIX', 'steadiness', 'steady' if sh < 3 else f'camera moves (~{sh:.0f}px per frame): use a tripod or lean the phone on something')

    # ---- sound
    if not info['audio']:
        add('FIX', 'sound', 'no audio track: check the microphone is allowed for the camera app')
    else:
        wav = os.path.splitext(a.clip)[0] + '_test16k.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.clip, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
        x, sr = sf.read(wav); os.remove(wav)
        hop = int(sr * 0.02); e = np.array([np.sqrt((x[i:i + hop] ** 2).mean() + 1e-12) for i in range(0, len(x) - hop, hop)])
        db = 20 * np.log10(e + 1e-9); speech = np.percentile(db, 90); noise = np.percentile(db, 10)
        if speech < -55:
            add('FIX', 'sound', 'silent: nothing recorded; check the mic and say a few lines in the test')
        else:
            lv = 'OK' if speech > -32 else ('WARN' if speech > -42 else 'FIX')
            add(lv, 'voice level', f'{speech:.0f} dB' + ('' if lv == 'OK' else ': bring the mic closer (phone mic within an arm, or a clip-on mic)'))
            snr = speech - noise
            lv = 'OK' if snr > 25 else ('WARN' if snr > 15 else 'FIX')
            add(lv, 'background noise', f'voice is {snr:.0f} dB above the room noise' + ('' if lv == 'OK' else
                ': turn off the fan/AC, close windows, or use a clip-on mic'))
            if (np.abs(x) > 0.99).mean() > 0.001:
                add('FIX', 'distortion', 'the voice is clipping (too loud): move the mic a little further away')

    icon = {'OK': ' OK ', 'WARN': 'WARN', 'FIX': 'FIX '}
    for lv, n, m in rows: print(f'{icon[lv]}  {n:17} {m}')
    fixes = sum(1 for r in rows if r[0] == 'FIX')
    print('\n' + ('Ready to film.' if not fixes else f'{fixes} thing(s) to fix before the real take.'))


if __name__ == '__main__':
    main()
