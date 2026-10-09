"""Mix the voiceover into the v11 audio track (video stream untouched).

Reads demo/vo/manifest.json: [{"file": seg01.mp3, "offset": 0.3}, ...].
Builds: ambient bed + foley events (as make_final_v11.audio_events), ducked
under each narration span, plus the decoded voice clips; the whole mix is
peak-normalised to -2.72 dBFS, then remuxed over the existing video stream.

Run: python3 demo/mix_voice.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from renderkit import LEVELS, ambient_bed, ffmpeg_exe, synth_event  # noqa: E402
from make_final_v11 import DUR, OUT_LOG, OUT_MP4, audio_events  # noqa: E402

VO_DIR = os.path.join(HERE, "vo")
MANIFEST = os.path.join(VO_DIR, "manifest.json")
WAV = os.path.join(HERE, "_v11_voice_mix.wav")
SR = 48000


def decode_clip(path: str) -> np.ndarray:
    raw = subprocess.run(
        [ffmpeg_exe(), "-v", "quiet", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def main():
    with open(MANIFEST, encoding="utf-8") as f:
        man = json.load(f)
    n = int(DUR * SR)

    # bed + foley, pre-normalisation (same recipe as the music-only mix)
    mix = ambient_bed(DUR, peak_dbfs=0.0, sr=SR) * 0.55
    rng = np.random.default_rng(11)
    for t0, kind, dur in audio_events():
        s = synth_event(kind, sr=SR, dur=dur, rng=rng) * LEVELS[kind]
        i0 = int(t0 * SR)
        if i0 >= n:
            continue
        i1 = min(n, i0 + len(s))
        mix[i0:i1] += s[: i1 - i0]

    # decode clips and measure them
    clips = [(m["offset"], decode_clip(os.path.join(VO_DIR, m["file"]))) for m in man]

    # duck the bed+foley under every narration span (disjoint spans, one pass)
    duck = np.ones(n)
    for off, clip in clips:
        i0 = int(off * SR)
        i1 = min(n, i0 + len(clip))
        d0 = max(0, i0 - int(0.25 * SR))
        d1 = min(n, i1 + int(0.35 * SR))
        duck[d0:d1] = np.minimum(duck[d0:d1], 0.45)
    e = int(0.25 * SR)
    from scipy.ndimage import uniform_filter1d
    duck = uniform_filter1d(duck, size=e)
    mix *= duck

    # add voice
    report = []
    for off, clip in clips:
        i0 = int(off * SR)
        i1 = min(n, i0 + len(clip))
        mix[i0:i1] += clip[: i1 - i0] * 0.9
        report.append((off, len(clip) / SR))
    for off, d in report:
        print(f"  vo @ {off:6.1f}s  dur {d:5.2f}s  end {off + d:6.1f}s")

    mix = mix / (np.max(np.abs(mix)) + 1e-9) * (10 ** (-2.72 / 20.0))
    pcm = np.clip(mix, -1.0, 1.0)
    with wave.open(WAV, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((pcm * 32767).astype("<i2").tobytes())

    tmp = OUT_MP4 + ".vo.mp4"
    subprocess.run(
        [ffmpeg_exe(), "-y", "-i", OUT_MP4, "-i", WAV,
         "-map", "0:v:0", "-map", "1:a:0",          # explicit: new audio replaces old
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-shortest", "-movflags", "+faststart", tmp],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(tmp, OUT_MP4)
    os.remove(WAV)
    with open(OUT_LOG, "a", encoding="utf-8") as f:
        f.write("audio v3: calm male voiceover added (10 segments, ducked bed+foley under\n")
        f.write("  narration), mix peak -2.72 dBFS; video stream copied; captions unchanged.\n")
    print(f"remuxed voiceover into {OUT_MP4}")


if __name__ == "__main__":
    main()
