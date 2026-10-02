"""
check_camera_stream.py — TB2 MJPEG 스트림 단계별 진단 (PC에서 실행)
사용: python tools/check_camera_stream.py [--host 172.30.1.28] [--port 8080]
단계: TCP 접속 → ustreamer /state → /snapshot → /stream 첫 프레임·fps → OpenCV 열기 시간
"""

import argparse
import http.client
import json
import socket
import sys
import time

TCP_TIMEOUT_S = 3.0
HTTP_TIMEOUT_S = 5.0
STREAM_SAMPLE_S = 3.0
JPEG_SOI = b"\xff\xd8"
MAX_BODY_BYTES = 2 * 1024 * 1024


def step(ok: bool, label: str, hint: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         → {hint}" if hint and not ok else ""))
    return ok


def check_tcp(host: str, port: int) -> bool:
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT_S):
            return step(True, f"TCP {host}:{port} 접속 {1000 * (time.monotonic() - t0):.0f} ms")
    except ConnectionRefusedError:
        return step(False, "TCP 접속 거부 (RST)", "로봇은 응답하나 8080 리슨 없음 → ustreamer 미기동/127.0.0.1 바인딩")
    except (socket.timeout, TimeoutError):
        return step(False, f"TCP 접속 {TCP_TIMEOUT_S:.0f}s 무응답 (패킷 drop)",
                    "로봇 오프라인·IP 변경(재부팅 후 DHCP)·ufw 방화벽 → ping, 'sudo ufw status'")
    except OSError as e:
        return step(False, f"TCP 오류 {e}", "PC Wi-Fi·IP 확인")


def http_get(host: str, port: int, path: str):
    conn = http.client.HTTPConnection(host, port, timeout=HTTP_TIMEOUT_S)
    t0 = time.monotonic()
    conn.request("GET", path)
    resp = conn.getresponse()
    # multipart(무한 스트림)면 본문을 끝까지 읽지 않음
    body = b"" if "multipart" in resp.getheader("Content-Type", "") else resp.read(MAX_BODY_BYTES)
    conn.close()
    return resp.status, body, 1000 * (time.monotonic() - t0)


def check_state(host: str, port: int) -> None:
    try:
        status, body, _ = http_get(host, port, "/state")
    except Exception as e:
        step(False, f"/state 요청 실패 ({type(e).__name__})", "HTTP 응답 없음 → 서버 프로세스 정지(hang) 의심")
        return
    if status != 200:
        print(f"  [INFO] /state HTTP {status} (ustreamer 아님 또는 구버전)")
        return
    try:
        src = json.loads(body)["result"]["source"]
    except (ValueError, KeyError):
        print("  [INFO] /state 형식 미확인")
        return
    online = bool(src.get("online"))
    step(online, f"ustreamer 소스 online={online} resolution={src.get('resolution')} "
                 f"captured_fps={src.get('captured_fps')}",
         "서버는 살아있으나 카메라 프레임 없음 → TB2에서 'tb2_services.sh diag' (Bayer 노드/레거시 미검출)")


def check_snapshot(host: str, port: int) -> None:
    try:
        status, body, ms = http_get(host, port, "/snapshot")
    except Exception as e:
        step(False, f"/snapshot 실패 ({type(e).__name__})")
        return
    step(status == 200 and body.startswith(JPEG_SOI),
         f"/snapshot HTTP {status}, {len(body)} bytes, {ms:.0f} ms",
         "503 = 소스 offline (카메라 프레임 없음)")


def check_stream(host: str, port: int) -> bool:
    conn = http.client.HTTPConnection(host, port, timeout=HTTP_TIMEOUT_S)
    try:
        t0 = time.monotonic()
        conn.request("GET", "/stream")
        resp = conn.getresponse()
        ctype = resp.getheader("Content-Type", "")
        step("multipart" in ctype, f"/stream HTTP {resp.status}, Content-Type={ctype}")
        frames, first_ms, buf = 0, None, b""
        while time.monotonic() - t0 < STREAM_SAMPLE_S + (first_ms or 0) / 1000:
            try:
                chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(4096)
            except (socket.timeout, TimeoutError):
                break  # 헤더 후 프레임 무송신 = 카메라 캡처 정지 (릴레이 OpenCV 타임아웃과 동일 증상)
            if not chunk:
                break
            buf += chunk
            n = buf.count(JPEG_SOI)
            if n and first_ms is None:
                first_ms = 1000 * (time.monotonic() - t0)
            frames += n
            buf = buf[-1:]  # 경계 걸친 SOI 대비
        if first_ms is None:
            return step(False, "첫 JPEG 프레임 미수신", "헤더만 오고 프레임 없음 → 카메라 캡처 정지")
        fps = frames / STREAM_SAMPLE_S
        step(True, f"첫 프레임 {first_ms:.0f} ms, 약 {fps:.1f} fps")
        if fps < 5:
            print("  [WARN] fps 낮음 → Wi-Fi 대역폭·카메라 노출(어두움)·CPU 인코딩(YUYV) 확인")
        return True
    except Exception as e:
        return step(False, f"/stream 실패 ({type(e).__name__}: {e})")
    finally:
        conn.close()


def check_opencv(url: str, open_timeout_ms: int) -> None:
    try:
        import cv2
    except ImportError:
        print("  [INFO] cv2 없음 → 생략")
        return
    t0 = time.monotonic()
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, open_timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000])
    open_ms = 1000 * (time.monotonic() - t0)
    ok, frame = cap.read() if cap.isOpened() else (False, None)
    cap.release()
    step(ok and frame is not None,
         f"OpenCV 열기 {open_ms:.0f} ms (제한 {open_timeout_ms} ms), 프레임 {None if frame is None else frame.shape}",
         "위 단계가 모두 PASS인데 여기만 FAIL → 릴레이 --camera-open-timeout-ms 상향")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="172.30.1.28")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--open-timeout-ms", type=int, default=8000)
    a = ap.parse_args()
    print(f"== 카메라 스트림 진단 http://{a.host}:{a.port}")
    print("[1] TCP")
    if not check_tcp(a.host, a.port):
        return 1
    print("[2] ustreamer 상태")
    check_state(a.host, a.port)
    print("[3] 스냅샷")
    check_snapshot(a.host, a.port)
    print("[4] MJPEG 스트림")
    if not check_stream(a.host, a.port):
        return 1
    print("[5] OpenCV (릴레이와 동일 경로)")
    check_opencv(f"http://{a.host}:{a.port}/stream", a.open_timeout_ms)
    return 0


if __name__ == "__main__":
    sys.exit(main())
