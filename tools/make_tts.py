"""
시연 영상 TTS 내레이션: video/NARRATION.md 표 → 구간별 mp3 (edge-tts) → 원본 영상에 얹은 사본 생성.

- 원본 영상은 수정하지 않는다. 결과: video/demo1_tts.mp4, 구간 음성: video/tts/segNN.mp3
- 문장이 구간보다 길면 말 속도를 RATE_STEP씩 올려 다시 합성 (최대 MAX_RATE).
- 원본 오디오(현장음)는 BG_VOLUME으로 낮춰 깔고 내레이션을 위에 섞는다.
실행: python tools/make_tts.py
"""

import asyncio
import os
import re
import subprocess

import edge_tts
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "video")
SCRIPT = os.path.join(V, "NARRATION.md")
SRC = os.path.join(V, "demo1(자막x).mp4")
OUT = os.path.join(V, "demo1_tts.mp4")
TTS_DIR = os.path.join(V, "tts")
FF = imageio_ffmpeg.get_ffmpeg_exe()

VOICE = "ko-KR-InJoonNeural"
BASE_RATE = 0          # %
RATE_STEP = 5          # %
MAX_RATE = 30          # %
BG_VOLUME = 0.25       # 현장음 비율
VOICE_VOLUME = 1.6


def load_segments():
    segs = []
    with open(SCRIPT, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|[^|]*\|\s*(.+?)\s*\|\s*$", line)
            if m:
                segs.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return segs


def duration(path):
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    h, mi, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr).groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


async def synth(text, rate, path):
    await edge_tts.Communicate(text, VOICE, rate=f"{rate:+d}%").save(path)


async def build_voices(segs):
    files = []
    for i, (start, end, text) in enumerate(segs, 1):
        path = os.path.join(TTS_DIR, f"seg{i:02d}.mp3")
        slot = end - start
        rate = BASE_RATE
        while True:
            await synth(text, rate, path)
            d = duration(path)
            if d <= slot or rate >= MAX_RATE:
                break
            rate += RATE_STEP
        flag = "" if d <= slot else "  ** 구간 초과: 문장을 줄이세요"
        print(f"seg{i:02d} {start:5.1f}-{end:5.1f}s  slot {slot:4.1f}s  voice {d:4.1f}s  rate {rate:+d}%{flag}")
        files.append((start, path))
    return files


def mix(files):
    cmd = [FF, "-y", "-loglevel", "error", "-i", SRC]
    for _, p in files:
        cmd += ["-i", p]
    parts = [f"[0:a]volume={BG_VOLUME}[bg]"]
    labels = ["[bg]"]
    for k, (start, _) in enumerate(files, 1):
        ms = int(start * 1000)
        parts.append(f"[{k}:a]aresample=48000,volume={VOICE_VOLUME},adelay={ms}|{ms}[v{k}]")
        labels.append(f"[v{k}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT]
    subprocess.run(cmd, check=True)


def main():
    os.makedirs(TTS_DIR, exist_ok=True)
    segs = load_segments()
    files = asyncio.run(build_voices(segs))
    mix(files)
    print("written", OUT)


if __name__ == "__main__":
    main()
