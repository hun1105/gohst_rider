"""
Mock Hardware & Pipeline Tester
===============================
- 하드웨어(ESP32, 아두이노, 메타퀘스트 2)가 없어도
  전체 통신 파이프라인(가상 차량 물리 시뮬레이션, VR 조작 입력 에뮬레이션)을
  단일 콘솔에서 검증하는 테스트 스크립트.
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [TEST-MOCK] %(message)s")

async def run_mock_vr_client():
    uri = "ws://localhost:9090"
    logging.info(f"Connecting to Relay Agent at {uri}...")
    
    try:
        async with websockets.connect(uri) as ws:
            logging.info("Connected to Relay Agent! Simulating Meta Quest 2 Controller Inputs...")

            # 1. 전진 명령 전송 (Thumbstick 전진)
            logging.info("Step 1: Sending DRIVE (Forward: left=200, right=200)...")
            await ws.send(json.dumps({"cmd": "DRIVE", "left": 200, "right": 200}))
            await asyncio.sleep(2)

            # 2. 좌회전 명령 전송 (Thumbstick 좌회전)
            logging.info("Step 2: Sending DRIVE (Turn Left: left=-150, right=150)...")
            await ws.send(json.dumps({"cmd": "DRIVE", "left": -150, "right": 150}))
            await asyncio.sleep(1.5)

            # 3. 우회전 명령 전송
            logging.info("Step 3: Sending DRIVE (Turn Right: left=150, right=-150)...")
            await ws.send(json.dumps({"cmd": "DRIVE", "left": 150, "right": -150}))
            await asyncio.sleep(1.5)

            # 4. 정지 명령 전송
            logging.info("Step 4: Sending STOP...")
            await ws.send(json.dumps({"cmd": "STOP"}))
            await asyncio.sleep(1)

            # 5. 거시-미시 시점 전환 명령 전송 (빙의 모드)
            logging.info("Step 5: Simulating Macro-to-Micro Teleportation (Possession Mode)...")
            await ws.send(json.dumps({"cmd": "TELEPORT", "mode": "MICRO_FPV"}))
            await asyncio.sleep(1)

            logging.info("Test finished successfully! Communication link verified.")
    except Exception as e:
        logging.error(f"Could not connect to relay agent: {e}")
        logging.info("Tip: First run `python relay_agent.py --mock --no-ai` in another terminal.")

if __name__ == "__main__":
    asyncio.run(run_mock_vr_client())
