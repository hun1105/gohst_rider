"""
화면 녹화 (시연 영상용 Unity 화면 캡처) — ffmpeg gdigrab, imageio-ffmpeg 내장 바이너리 사용.

실행 예:
  python tools/record_screen.py --out video/unity_01.mp4            # 전체 화면
  python tools/record_screen.py --out video/unity_01.mp4 --window "Unity"   # 제목에 'Unity'가 든 창만
정지: 같은 폴더에 <출력이름>.stop 파일을 만들거나 Ctrl+C.  (--max 초가 지나도 자동 정지)
중간에 끊겨도 영상이 깨지지 않도록 .mkv로 녹화한 뒤 끝나면 .mp4로 옮겨 담는다.
"""

import argparse
import ctypes
import os
import subprocess
import sys
import time

import imageio_ffmpeg

POLL_S = 0.5


def find_window_title(part: str) -> str | None:
    """제목에 part가 들어간 첫 번째 보이는 창의 전체 제목."""
    user32 = ctypes.windll.user32
    found: list[str] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if part.lower() in buf.value.lower():
                    found.append(buf.value)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--window", default=None, help="창 제목 일부 (없으면 전체 화면)")
    ap.add_argument("--max", type=int, default=600, help="최대 녹화 초")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    base, _ = os.path.splitext(out)
    mkv, stop = base + ".mkv", base + ".stop"
    if os.path.exists(stop):
        os.remove(stop)

    src = "desktop"
    if a.window:
        title = find_window_title(a.window)
        if not title:
            print(f"창을 찾지 못함: {a.window}", file=sys.stderr)
            return 1
        src = f"title={title}"
        print("녹화 창:", title)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", str(a.fps), "-draw_mouse", "1", "-i", src,
           "-t", str(a.max), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", mkv]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    print(f"녹화 시작 → {mkv}  (정지: {stop} 파일 생성 또는 Ctrl+C)", flush=True)
    try:
        while proc.poll() is None:
            if os.path.exists(stop):
                break
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    if proc.poll() is None:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=30)
    dur = time.time() - t0
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", mkv, "-c", "copy", "-movflags", "+faststart", out], check=True)
    os.remove(mkv)
    if os.path.exists(stop):
        os.remove(stop)
    print(f"녹화 끝: {out}  ({dur:.1f}초, {os.path.getsize(out) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
