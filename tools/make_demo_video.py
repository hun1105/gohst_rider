"""
시연 영상 1차 편집 (자막 없음): video/ 의 실물 휴대폰 영상 + Unity·Quest 화면 녹화를 장면별로 나란히 합쳐 이어 붙인다.

장면 (시각은 각 파일 안의 초, 로봇이 움직이기 시작한 순간으로 맞춤):
  1. 2대 만남 정지   : 실물(실물 로봇2대 멈춤) | 관제 맵(real/unity_c1_take1)
  2. 상자 → 정지      : 실물(실물 로봇1대 긴급정지) | 관제 맵(real/unity_c2_take1)
  3. VR 원격 개입     : Quest 콕핏(real/quest_c3_take1) 크게 + 관제 맵(real/unity_c3_take1) + 조작자(실물 관제사 운용)
실행: python tools/make_demo_video.py  → video/demo_v1.mp4
"""

import os
import subprocess

import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "video")
OUT_DIR = os.path.join(V, "_edit")
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 30
BG = "0x111111"

# Unity 창 녹화에서 에디터 메뉴·상태줄을 빼고 Game 화면만 (가운데 16:9)
UNITY_CROP_1920 = "crop=1000:562:460:219"     # 1920x966 녹화, 로봇 주변 확대
UNITY_CROP_1250 = "crop=900:506:175:200"      # 1250x948 녹화 (창을 줄여 찍은 컷 3), 로봇 주변 확대
QUEST_CROP = "crop=380:226:22:62"             # 미러 화면 중 콕핏 카메라 패널(정지 배너·탈출 안내 포함)만


def src(name):
    return os.path.join(V, name)


def run(cmd):
    subprocess.run([FF, "-y", "-loglevel", "error"] + cmd, check=True)


def side_by_side(out, left, left_ss, right, right_ss, right_crop, dur):
    """왼쪽 실물, 오른쪽 관제 맵 (각 900x506), 실물이 짧으면 마지막 프레임 유지."""
    pw, ph, y = 900, 506, (H - 506) // 2
    fc = (f"color=c={BG}:s={W}x{H}:d={dur}:r={FPS}[bg];"
          f"[0:v]setpts=PTS-STARTPTS,scale={pw}:{ph},tpad=stop_mode=clone:stop_duration={dur}[a];"
          f"[1:v]setpts=PTS-STARTPTS,{right_crop},scale={pw}:{ph},tpad=stop_mode=clone:stop_duration={dur}[b];"
          f"[bg][a]overlay=40:{y}:shortest=0[t];[t][b]overlay={W - 40 - pw}:{y}[v]")
    run(["-ss", str(left_ss), "-t", str(dur), "-i", src(left),
         "-ss", str(right_ss), "-t", str(dur), "-i", src(right),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), "-r", str(FPS),
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-an", out])


def vr_scene(out, quest, unity, phone, ss_screen, ss_phone, dur):
    """왼쪽 Quest 콕핏 크게, 오른쪽 위 관제 맵, 오른쪽 아래 조작자."""
    qw, qh = 1200, 714
    sw, sh = 640, 347
    x0 = (W - (qw + 20 + sw)) // 2
    y0 = (H - qh) // 2
    fc = (f"color=c={BG}:s={W}x{H}:d={dur}:r={FPS}[bg];"
          f"[0:v]setpts=PTS-STARTPTS,{QUEST_CROP},scale={qw}:{qh},tpad=stop_mode=clone:stop_duration={dur}[q];"
          f"[1:v]setpts=PTS-STARTPTS,{UNITY_CROP_1250},scale={sw}:{sh},tpad=stop_mode=clone:stop_duration={dur}[u];"
          f"[2:v]setpts=PTS-STARTPTS,scale={sw}:{sh},tpad=stop_mode=clone:stop_duration={dur}[p];"
          f"[bg][q]overlay={x0}:{y0}[t1];[t1][u]overlay={x0 + qw + 20}:{y0}[t2];"
          f"[t2][p]overlay={x0 + qw + 20}:{y0 + qh - sh}[v]")
    run(["-ss", str(ss_screen), "-t", str(dur), "-i", src(quest),
         "-ss", str(ss_screen), "-t", str(dur), "-i", src(unity),
         "-ss", str(ss_phone), "-t", str(dur), "-i", src(phone),
         "-filter_complex", fc, "-map", "[v]", "-t", str(dur), "-r", str(FPS),
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-an", out])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    s1, s2, s3 = (os.path.join(OUT_DIR, f"scene{i}.mp4") for i in (1, 2, 3))
    # 1. 실물 8.3초 출발 ↔ Unity 90.5초 출발
    side_by_side(s1, "실물 로봇2대 멈춤.mp4", 2.0, "real/unity_c1_take1.mp4", 84.2, UNITY_CROP_1920, 14)
    # 2. 실물 12.5초 출발 ↔ Unity 9초 출발
    side_by_side(s2, "실물 로봇1대 긴급정지.mp4", 8.0, "real/unity_c2_take1.mp4", 4.5, UNITY_CROP_1920, 16)
    # 3. 콕핏 진입(78초) 직후부터, TB1 인터록 구간(약 116초) 전까지
    vr_scene(s3, "real/quest_c3_take1.mp4", "real/unity_c3_take1.mp4", "실물 관제사 운용.mp4", 77, 4.0, 31)

    lst = os.path.join(OUT_DIR, "concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in (s1, s2, s3):
            f.write(f"file '{s}'\n")
    out = os.path.join(V, "demo_v1.mp4")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
    print("written", out)


if __name__ == "__main__":
    main()
