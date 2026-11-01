"""Face tracking (YuNet) and person cut-out (MediaPipe Selfie Segmenter).
Models come from the vendored claude-video-effects repo (MIT / Apache-2.0)."""
import os, subprocess, math
import numpy as np, cv2
from common import ROOT

MODELS = os.path.join(ROOT, 'vendor', 'claude-video-effects', 'models')


def read_frames(path, w, h, start=0.0, dur=None, fps=None):
    """Yield (index_from_start, rgb) frames, scaled to cover w x h, starting at `start` seconds."""
    vf = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
    if fps: vf = f'fps={fps},' + vf
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{start:.3f}', '-i', path]
    if dur: cmd += ['-t', f'{dur:.3f}']
    cmd += ['-vf', vf + ',format=rgb24', '-f', 'rawvideo', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 8)
    n = w * h * 3; i = 0
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            yield i, np.frombuffer(b, np.uint8).reshape(h, w, 3); i += 1
    finally:
        p.stdout.close(); p.wait()


def smooth(arr, fps, tau=0.25):
    arr = np.array(arr, np.float64)
    a = 1 - math.exp(-1 / (fps * tau))
    for i in range(1, len(arr)): arr[i] = arr[i - 1] + a * (arr[i] - arr[i - 1])
    for i in range(len(arr) - 2, -1, -1): arr[i] = arr[i + 1] + a * (arr[i] - arr[i + 1])
    return arr


def face_track(src, info, ranges, step=3, short=360):
    """Return a function t_src -> (cx, cy, fw) in 0..1 frame units (fw = face width / frame width)."""
    W, H = (short, int(round(short * info['h'] / info['w']))) if info['w'] <= info['h'] else (int(round(short * info['w'] / info['h'])), short)
    W -= W % 2; H -= H % 2
    fd = cv2.FaceDetectorYN.create(os.path.join(MODELS, 'yunet.onnx'), '', (W, H), 0.6, 0.3, 20)
    ts, vals = [], []
    fps = info['fps']
    for a, b in ranges:
        for i, fr in read_frames(src, W, H, a, b - a, fps=fps / step):
            _, f = fd.detect(cv2.cvtColor(fr, cv2.COLOR_RGB2BGR))
            if f is not None and len(f):
                r = max(f, key=lambda r: r[2] * r[3] * r[-1])
                ts.append(a + i * step / fps); vals.append(((r[0] + r[2] / 2) / W, (r[1] + r[3] / 2) / H, r[2] / W))
    if not vals:
        return lambda t: (0.5, 0.38, 0.15)
    order = np.argsort(ts); ts = np.array(ts)[order]; vals = smooth(np.array(vals)[order], fps / step, 0.35)

    def at(t):
        return tuple(float(np.interp(t, ts, vals[:, k])) for k in range(3))
    return at


class Segmenter:
    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        self.mp = mp
        self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=os.path.join(MODELS, 'selfie_segmenter.tflite')),
            running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True, output_category_mask=False))
        self.prev = None; self.last_ms = -1

    def __call__(self, rgb, ms):
        ms = max(int(ms), self.last_ms + 1); self.last_ms = ms
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        m = self.seg.segment_for_video(img, ms).confidence_masks[-1].numpy_view().astype(np.float32)
        m = m.reshape(m.shape[0], m.shape[1])
        if m.shape[:2] != rgb.shape[:2]: m = cv2.resize(m, (rgb.shape[1], rgb.shape[0]))
        m = np.clip((m - 0.5) * 1.8 + 0.5, 0, 1)
        if self.prev is not None and self.prev.shape == m.shape: m = 0.6 * m + 0.4 * self.prev
        self.prev = m
        return m


def masks_for(src, info, windows, short=320):
    """Person masks for source-time windows. Returns dict: source frame index -> uint8 mask (small)."""
    W, H = (short, int(round(short * info['h'] / info['w']))) if info['w'] <= info['h'] else (int(round(short * info['w'] / info['h'])), short)
    W -= W % 2; H -= H % 2
    out = {}; fps = info['fps']
    for a, b in windows:
        sg = Segmenter()
        for i, fr in read_frames(src, W, H, a, b - a):
            fi = int(round(a * fps)) + i
            out[fi] = (sg(fr, (a + i / fps) * 1000) * 255).astype(np.uint8)
    return out
