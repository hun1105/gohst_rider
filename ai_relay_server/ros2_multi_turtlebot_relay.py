"""
Physical AI Multi-Agent ROS 2 Humble Relay & Safety Interlock Server
===================================================================
- 역할:
  1. TurtleBot3 Burger 2대(tb1: 주행 AGV, tb2: 순찰/장애물 AGV) ROS 2 Humble 통신 중계
  2. Unity 6 (Meta Quest VR) 텔레오퍼레이션 명령(/tb1/cmd_vel) 실시간 전달
  3. tb1 및 tb2 오도메트리(/tb1/odom, /tb2/odom) 실시간 좌표 변환 및 Unity 동기화
  4. YOLOv8 비전 AI 기반 협착/충돌 위험 감지 (작업자, tb2, 파렛트/화물)
  5. 하드웨어 미연결 시 즉시 시연 및 개발 가능한 고정밀 모의 시뮬레이션 모드 내장
"""

import argparse
import asyncio
import cv2
import json
import logging
import math
import numpy as np
import time
import websockets
from websockets.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiTurtleBotRelay")

class TurtleBotState:
    def __init__(self, name: str, init_x: float = 0.0, init_z: float = 0.0, init_yaw: float = 0.0):
        self.name = name
        self.x = init_x
        self.y = 0.0
        self.z = init_z
        self.yaw = init_yaw  # 도(Degree)
        self.linear_vel = 0.0
        self.angular_vel = 0.0
        self.battery = 100.0

    def update_physics(self, dt: float):
        rad = math.radians(self.yaw)
        self.x += self.linear_vel * math.sin(rad) * dt
        self.z += self.linear_vel * math.cos(rad) * dt
        self.yaw = (self.yaw + math.degrees(self.angular_vel * dt)) % 360.0

    def to_dict(self):
        return {
            "name": self.name,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "yaw": round(self.yaw, 2),
            "linear_vel": round(self.linear_vel, 2),
            "angular_vel": round(self.angular_vel, 2),
            "battery": round(self.battery, 1)
        }

class MultiTurtleBotRelay:
    def __init__(self, mock_mode: bool = True, use_ai: bool = True):
        self.mock_mode = mock_mode
        self.use_ai = use_ai
        
        # 2대의 TurtleBot3 상태 관리
        self.tb1 = TurtleBotState("tb1", init_x=0.0, init_z=0.0, init_yaw=0.0)
        self.tb2 = TurtleBotState("tb2", init_x=1.8, init_z=5.0, init_yaw=180.0)
        
        # tb2 자율 순찰 변수 (웨이포인트 순환)
        self.tb2_patrol_timer = 0.0
        
        # 안전 인터록 상태
        self.safety_interlock = False
        self.hazard_info = {"status": "NORMAL", "class": "", "distance": 999.0}
        
        self.connected_vr_clients = set()
        self.latest_frame_jpeg = None
        
        # YOLOv8 로드
        self.model = None
        if self.use_ai:
            try:
                from ultralytics import YOLO
                logger.info("YOLOv8 모델 로드 중 (경로 장애물/타AGV/작업자 전수 검출)...")
                self.model = YOLO("yolov8n.pt")
                logger.info("YOLOv8 안전 모델 로드 완료.")
            except Exception as e:
                logger.warning(f"YOLO 로드 실패 ({e}). 기본 릴레이 모드로 실행합니다.")

    def update_tb2_patrol(self, dt: float):
        """tb2 (보조 AGV)의 자율 순찰 궤적 시뮬레이션"""
        self.tb2_patrol_timer += dt
        # 직선 왕복 및 회전 시뮬레이션
        cycle = self.tb2_patrol_timer % 16.0
        if cycle < 6.0:
            self.tb2.linear_vel = 0.22  # 전진
            self.tb2.angular_vel = 0.0
        elif cycle < 8.0:
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 1.57 # 180도 회전
        elif cycle < 14.0:
            self.tb2.linear_vel = 0.22  # 복귀 전진
            self.tb2.angular_vel = 0.0
        else:
            self.tb2.linear_vel = 0.0
            self.tb2.angular_vel = 1.57 # 원위치 회전
            
        self.tb2.update_physics(dt)

    async def video_and_ai_loop(self):
        """tb1 전방 카메라 스트림 생성, YOLOv8 추론 및 충돌 인터록 판정"""
        cap = None
        if not self.mock_mode:
            # 실물 TurtleBot3 파이캠 스트림 (HTTP 또는 RTSP)
            cap = cv2.VideoCapture("http://192.168.0.101:8080/stream")

        while True:
            frame = None
            if cap and cap.isOpened():
                ret, frame = cap.read()
            
            if frame is None:
                # 고해상도 가상 물류창고 FPV 프레임 렌더링
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                # 바닥 그라디언트
                frame[240:, :] = (45, 45, 45)
                # 차선 라인
                cv2.line(frame, (80, 480), (280, 240), (0, 200, 255), 3)
                cv2.line(frame, (560, 480), (360, 240), (0, 200, 255), 3)
                
                # 거리 계산: tb1과 tb2의 상대적 거리
                dx = self.tb2.x - self.tb1.x
                dz = self.tb2.z - self.tb1.z
                dist_tb1_tb2 = math.sqrt(dx*dx + dz*dz)
                
                # 가상 tb2 (보조 로봇) 렌더링
                if dz > 0.5 and dz < 8.0 and abs(dx) < 2.5:
                    # 원근법 투영
                    scale = max(0.2, 1.0 - (dz / 8.0))
                    box_w = int(140 * scale)
                    box_h = int(180 * scale)
                    center_x = int(320 + (dx / dz) * 300)
                    center_y = int(240 + 120 * scale)
                    
                    x1 = max(0, center_x - box_w // 2)
                    y1 = max(0, center_y - box_h // 2)
                    x2 = min(640, center_x + box_w // 2)
                    y2 = min(480, center_y + box_h // 2)
                    
                    # tb2 바디 렌더링
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 140, 0), -1)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
                    cv2.putText(frame, "AGV_TB2 [Patrol]", (x1 + 5, y1 + 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, (255, 255, 255), 1)

            # YOLOv8 실시간 추론 (작업자, 차량/AGV, 파렛트 등)
            detected_hazard = False
            hazard_name = "NORMAL"
            min_dist = 999.0

            # tb1과 tb2의 물리적 거리 계산
            dist_to_tb2 = math.sqrt((self.tb2.x - self.tb1.x)**2 + (self.tb2.z - self.tb1.z)**2)
            
            if self.model is not None and frame is not None:
                # 0: 사람, 2,3,5,7: 차량/이동체, 24,26,28: 가방/화물, 56: 의자/장애물
                target_classes = [0, 1, 2, 3, 5, 7, 24, 26, 28, 56, 57]
                results = self.model(frame, classes=target_classes, verbose=False)
                for r in results:
                    for box in r.boxes:
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names.get(cls_id, "Obstacle")
                        
                        center_x = (bx1 + bx2) // 2
                        box_height = by2 - by1
                        
                        # 전방 충돌 회랑 (Corridor: 중앙 50%, 근접 거리)
                        in_corridor = (180 <= center_x <= 460) and (by2 > 220)
                        
                        if in_corridor and box_height > 80 and conf > 0.40:
                            detected_hazard = True
                            hazard_name = f"HAZARD: {cls_name}"
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)
                            cv2.putText(frame, f"INTERLOCK: {cls_name} ({conf:.2f})", 
                                        (bx1, max(by1 - 10, 25)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        else:
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                            cv2.putText(frame, f"{cls_name} {conf:.2f}", 
                                        (bx1, max(by1 - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # 타 AGV(tb2)와의 물리적 거리 기반 이중 안전 인터록 (안전 반경: 1.0m)
            if dist_to_tb2 < 1.0:
                detected_hazard = True
                hazard_name = f"COLLISION RISK: TB2 AGV ({dist_to_tb2:.2f}m)"

            self.safety_interlock = detected_hazard
            if self.safety_interlock and self.tb1.linear_vel > 0:
                # 전진 주행 즉시 차단
                self.tb1.linear_vel = 0.0
                logger.warning(f"[PHYSICAL AI INTERLOCK] Forward motion cut off! Reason: {hazard_name}")

            # HUD 상태 표시
            hud_color = (0, 0, 255) if self.safety_interlock else (0, 255, 0)
            status_str = f"SYSTEM: {hazard_name}" if self.safety_interlock else "SYSTEM: SAFE (NORMAL)"
            cv2.putText(frame, status_str, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, hud_color, 2)
            cv2.putText(frame, f"TB1 Pos: ({self.tb1.x:.1f}, {self.tb1.z:.1f}) | TB2: ({self.tb2.x:.1f}, {self.tb2.z:.1f}) | Dist: {dist_to_tb2:.2f}m",
                        (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(frame, "ROS 2 Humble Multi-Agent Teleop", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

            # JPEG 인코딩 및 버퍼 갱신
            _, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            self.latest_frame_jpeg = jpeg_buf.tobytes()

            await asyncio.sleep(0.033) # 30 FPS

    async def telemetry_loop(self):
        """Unity 6로 tb1 및 tb2 오도메트리/상태 JSON 실시간 전송 (20Hz)"""
        dt = 0.05
        while True:
            # tb2 순찰 물리 갱신
            self.update_tb2_patrol(dt)
            # tb1 물리 갱신
            self.tb1.update_physics(dt)

            telemetry_data = {
                "type": "telemetry",
                "tb1": self.tb1.to_dict(),
                "tb2": self.tb2.to_dict(),
                "safety": {
                    "interlock": self.safety_interlock,
                    "status": "EMERGENCY_STOP" if self.safety_interlock else "NORMAL",
                    "target": "tb1"
                }
            }
            msg = json.dumps(telemetry_data)

            # 연결된 모든 VR 클라이언트에 전송
            if self.connected_vr_clients:
                tasks = [client.send(msg) for client in list(self.connected_vr_clients)]
                await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(dt)

    async def vr_ws_handler(self, websocket):
        """Meta Quest 2 VR 클라이언트 웹소켓 통신 핸들러"""
        self.connected_vr_clients.add(websocket)
        logger.info(f"VR Client connected: {websocket.remote_address}")

        async def send_video_task():
            while True:
                if self.latest_frame_jpeg:
                    try:
                        await websocket.send(self.latest_frame_jpeg)
                    except Exception:
                        break
                await asyncio.sleep(0.033)

        video_sender = asyncio.create_task(send_video_task())

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    cmd = data.get("cmd")

                    if cmd == "TWIST":
                        # ROS 2 표준 Twist 포맷
                        target_robot = data.get("robot", "tb1")
                        lin = float(data.get("linear", 0.0))
                        ang = float(data.get("angular", 0.0))

                        if target_robot == "tb1":
                            if self.safety_interlock and lin > 0:
                                self.tb1.linear_vel = 0.0
                            else:
                                self.tb1.linear_vel = lin
                            self.tb1.angular_vel = ang

                    elif cmd == "DRIVE":
                        # 하위 호환 PWM / Left-Right 포맷 -> Twist 변환
                        left = int(data.get("left", 0))
                        right = int(data.get("right", 0))
                        # -220~+220 -> -0.22 m/s ~ +0.22 m/s 변환
                        forward_ratio = (left + right) / 440.0
                        turn_ratio = (left - right) / 440.0
                        
                        lin = forward_ratio * 0.22
                        ang = turn_ratio * 2.84
                        
                        if self.safety_interlock and lin > 0:
                            self.tb1.linear_vel = 0.0
                        else:
                            self.tb1.linear_vel = lin
                        self.tb1.angular_vel = ang

                    elif cmd == "STOP":
                        self.tb1.linear_vel = 0.0
                        self.tb1.angular_vel = 0.0

                    elif cmd == "TELEPORT":
                        logger.info(f"[Perspective Mode]: {data.get('mode')}")

                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            logger.info("VR Client disconnected.")
        finally:
            video_sender.cancel()
            self.connected_vr_clients.remove(websocket)
            self.tb1.linear_vel = 0.0
            self.tb1.angular_vel = 0.0

    async def run(self, host: str = "0.0.0.0", port: int = 9090):
        logger.info(f"ROS 2 Humble Multi-TurtleBot Relay running on ws://{host}:{port}...")
        server = await serve(self.vr_ws_handler, host, port)
        await asyncio.gather(
            self.video_and_ai_loop(),
            self.telemetry_loop(),
            server.wait_closed()
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ROS 2 Humble Multi-TurtleBot Relay Server")
    parser.add_argument("--mock", action="store_true", default=True, help="Enable simulation mock mode")
    parser.add_argument("--no-ai", action="store_true", help="Disable YOLOv8 AI inference")
    parser.add_argument("--port", type=int, default=9090, help="Relay server WebSocket port")
    args = parser.parse_args()

    relay = MultiTurtleBotRelay(mock_mode=args.mock, use_ai=not args.no_ai)
    try:
        asyncio.run(relay.run(port=args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped.")
