# Third-party components

| Component | Where | Licence |
|---|---|---|
| claude-video-effects by Vibha Ramprakash (@vibha.in.progress) | downloaded by `setup.sh` into `vendor/`, pinned to commit 99c9a33 | MIT |
| YuNet face detector | `vendor/claude-video-effects/models/yunet.onnx` | MIT |
| MediaPipe Selfie Segmenter | `vendor/claude-video-effects/models/selfie_segmenter.tflite` | Apache 2.0 |
| Inter (Black, ExtraBold) | `fonts/` | SIL OFL 1.1 (`fonts/OFL-Inter.txt`) |
| Poppins (Bold, Medium) | `fonts/` | SIL OFL 1.1 (`fonts/OFL-Poppins.txt`) |
| Kokoro-82M via kokoro-onnx | downloaded on first voice-over to `~/.cache/aarvan-video-kit/` | Apache 2.0 / MIT |
| faster-whisper | pip | MIT |
| NVIDIA Parakeet TDT 0.6B v2 (sherpa-onnx int8 export) | downloaded on demand from k2-fsa/sherpa-onnx GitHub releases to `~/.cache/aarvan-video-kit/asr` | CC-BY-4.0 (model), Apache 2.0 (sherpa-onnx) |
| Aarvan Labs logo (`brand/logo.png`) | brand asset | © Aarvan Labs, not covered by the MIT licence |

The music and sound effects are synthesised by `kit/music.py`. They're original, so there's nothing to license.
