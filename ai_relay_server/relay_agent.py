"""
Physical AI Relay & Safety Intervention Agent
==============================================
- 역할:
  1. Meta Quest 2 (Unity)와 RC AGV (ESP32-CAM/Arduino) 간 실시간 통신 브리지
  2. 실시간 영상 수신 및 AI 안전 관제 (YOLOv8 기반 사람/장애물 감지)
  3. 작업자 충돌 위험 감지 시 VR 조작 자동 개입 및 비상 감속 (Shared Autonomy)
  4. 하드웨어 미보유 시 가상 테스트를 위한 Mock 모드 내장 (--mock 플래그)
"""

import argparse
import asyncio
import cv2
import json
import logging
import numpy as np
import websockets
from websockets.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RelayAgent")

class PhysicalAIAgent:
    def __init__(self, esp32_ip: str, mock_mode: bool = False, use_ai: bool = True):
        self.esp32_ip = esp32_ip
        self.mock_mode = mock_mode
        self.use_ai = use_ai
        
        self.latest_frame_jpeg = None
        self.esp32_ws = None
        self.connected_vr_clients = set()
        
        # 안전 제어 상태 변수
        self.safety_override = False
        self.detected_hazards = []
        self.current_speed_left = 0
        self.current_speed_right = 0
        
        # YOLO 모델 로드 (옵션)
        self.model = None
        if self.use_ai:
            try:
                from ultralytics import YOLO
                logger.info("Loading YOLOv8 nano model for safety interlock...")
                self.model = YOLO("yolov8n.pt")
                logger.info("YOLOv8 model loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not load YOLO: {e}. Running in pure relay mode.")

    async def connect_to_esp32(self):
        """ESP32-CAM WebSocket 연결 유지 (재연결 지원)"""
        if self.mock_mode:
            logger.info("[Mock] Running in software simulation mode. Skipping ESP32 hardware connection.")
            return

        uri = f"ws://{self.esp32_ip}/ws"
        while True:
            try:
                logger.info(f"Connecting to ESP32 at {uri}...")
                async with websockets.connect(uri) as ws:
                    self.esp32_ws = ws
                    logger.info("Connected to ESP32-CAM WebSocket.")
                    while True:
                        msg = await ws.recv()
                        # 하드웨어 센서 텔레메트리 수신 처리 가능
                        logger.debug(f"ESP32 telemetry: {msg}")
            except Exception as e:
                logger.warning(f"ESP32 connection lost: {e}. Retrying in 2 seconds...")
                self.esp32_ws = None
                await asyncio.sleep(2)

    async def send_command_to_car(self, cmd_type: str, left: int, right: int):
        """명령을 검증하고 차량으로 전달 (AI 안전 개입 포함)"""
        if self.safety_override and (left > 0 or right > 0):
            logger.warning("[SAFETY INTERVENTION] Obstacle ahead! Blocking forward command.")
            left = 0
            right = 0

        self.current_speed_left = left
        self.current_speed_right = right

        msg = f"SPEED,{left},{right}"
        if self.mock_mode:
            logger.info(f"[Mock Car] Received Drive Command -> Left: {left}, Right: {right}")
            return

        if self.esp32_ws:
            try:
                await self.esp32_ws.send(msg)
            except Exception as e:
                logger.error(f"Failed to send to ESP32: {e}")

    async def video_capture_loop(self):
        """영상 스트림 수신 및 AI 위험성 평가 루프"""
        if self.mock_mode:
            stream_src = 0  # 기본 웹캠 또는 가상 그래픽 생성
        else:
            stream_src = f"http://{self.esp32_ip}:81/stream"

        cap = cv2.VideoCapture(stream_src)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                # 스트림 실패 시 가상 프레임 생성
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "NO HARDWARE CAMERA STREAM", (50, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.putText(frame, "Running in Simulation / Mock Mode", (50, 280),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                await asyncio.sleep(0.05)
            else:
                frame = cv2.resize(frame, (640, 480))

            # AI 추론 (작업자, 타 AGV/차량, 경로상 모든 장애물 전수 감지)
            hazard_detected = False
            hazard_label = ""
            if self.model is not None and frame is not None:
                # 사람(0), 차량/AGV(2,3,5,7), 화물/박스(24,26,28,56,57) 등 경로 방해 객체 전수 추론
                target_classes = [0, 1, 2, 3, 5, 7, 24, 26, 28, 56, 57]
                results = self.model(frame, classes=target_classes, verbose=False)
                for r in results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names.get(cls_id, "obstacle")

                        box_height = y2 - y1
                        box_center_x = (x1 + x2) // 2

                        # 차량 주행 경로 전방 회랑(Corridor: x축 중앙 60%, 하단부) 충돌 위험 판정
                        is_in_corridor = (160 <= box_center_x <= 480) and (y2 > 200)

                        if is_in_corridor and box_height > 100 and conf > 0.45:
                            hazard_detected = True
                            if cls_id == 0:
                                hazard_label = "DANGER: WORKER DETECTED"
                            elif cls_id in [2, 3, 5, 7]:
                                hazard_label = f"DANGER: AGV/VEHICLE ({cls_name})"
                            else:
                                hazard_label = f"DANGER: PATH OBSTACLE ({cls_name})"

                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                            cv2.putText(frame, hazard_label, (x1, max(y1 - 10, 25)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
                        else:
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{cls_name} {conf:.2f}", (x1, max(y1 - 5, 15)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            self.safety_override = hazard_detected
            if hazard_detected and (self.current_speed_left > 0 or self.current_speed_right > 0):
                # 즉시 강제 정지 발송
                await self.send_command_to_car("STOP", 0, 0)

            # 상태 HUD 표시
            status_text = "STATUS: SAFE" if not self.safety_override else "STATUS: HAZARD INTERVENED"
            color = (0, 255, 0) if not self.safety_override else (0, 0, 255)
            cv2.putText(frame, status_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"L:{self.current_speed_left} R:{self.current_speed_right}",
                        (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # JPEG 인코딩
            _, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self.latest_frame_jpeg = jpeg_buf.tobytes()

            await asyncio.sleep(0.033) # 약 30 FPS 유지

    async def vr_ws_handler(self, websocket):
        """Meta Quest 2 (Unity) 클라이언트 웹소켓 통신 핸들러"""
        self.connected_vr_clients.add(websocket)
        logger.info(f"VR Client connected: {websocket.remote_address}")

        async def send_video_task():
            while True:
                if self.latest_frame_jpeg:
                    try:
                        await websocket.send(self.latest_frame_jpeg)
                    except Exception:
                        break
                await asyncio.sleep(0.04)

        video_sender = asyncio.create_task(send_video_task())

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    cmd = data.get("cmd")
                    if cmd == "DRIVE":
                        left = int(data.get("left", 0))
                        right = int(data.get("right", 0))
                        await self.send_command_to_car("DRIVE", left, right)
                    elif cmd == "STOP":
                        await self.send_command_to_car("STOP", 0, 0)
                    elif cmd == "TELEPORT":
                        logger.info(f"[Perspective Switch] Mode changed: {data.get('mode')}")
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("VR Client disconnected.")
        finally:
            video_sender.cancel()
            self.connected_vr_clients.remove(websocket)
            await self.send_command_to_car("STOP", 0, 0)

    async def run(self, host: str = "0.0.0.0", port: int = 9090):
        logger.info(f"Starting Physical AI Relay Server on ws://{host}:{port}...")
        server = await serve(self.vr_ws_handler, host, port)
        
        tasks = [
            asyncio.create_task(self.video_capture_loop()),
            asyncio.create_task(self.connect_to_esp32()),
            server.wait_closed()
        ]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Physical AI Relay & Safety Intervention Agent")
    parser.add_argument("--esp32-ip", type=str, default="192.168.4.1", help="ESP32-CAM IP address")
    parser.add_argument("--mock", action="store_true", help="Run without physical hardware in mock simulation mode")
    parser.add_argument("--no-ai", action="store_true", help="Disable YOLO model")
    parser.add_argument("--port", type=int, default=9090, help="Relay server WebSocket port")
    args = parser.parse_args()

    agent = PhysicalAIAgent(esp32_ip=args.esp32_ip, mock_mode=args.mock, use_ai=not args.no_ai)
    try:
        asyncio.run(agent.run(port=args.port))
    except KeyboardInterrupt:
        logger.info("Server terminated by user.")
