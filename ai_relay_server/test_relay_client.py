import asyncio
import json
import websockets

async def test():
    uri = 'ws://127.0.0.1:9090'
    print('Connecting to relay...')
    async with websockets.connect(uri) as ws:
        print('Connected successfully!')
        # Send DRIVE/TWIST command
        await ws.send(json.dumps({'cmd': 'TWIST', 'robot': 'tb1', 'linear': 0.15, 'angular': 0.0}))
        got_image = False
        got_telemetry = False
        for _ in range(30):
            msg = await ws.recv()
            if isinstance(msg, bytes):
                got_image = True
                print(f'Received Image frame: {len(msg)} bytes')
            elif isinstance(msg, str):
                data = json.loads(msg)
                if data.get('type') == 'telemetry':
                    got_telemetry = True
                    tb1 = data.get('tb1')
                    tb2 = data.get('tb2')
                    safety = data.get('safety')
                    print(f'Received Telemetry -> TB1: x={tb1["x"]}, z={tb1["z"]}, vel={tb1["linear_vel"]} | TB2: x={tb2["x"]}, z={tb2["z"]} | Safety: {safety["status"]}')
            if got_image and got_telemetry:
                break
        assert got_image and got_telemetry, 'Test failed: image or telemetry missing'
        print('VERIFICATION SUCCESSFUL: Both FPV video and Multi-TurtleBot telemetry functioning!')

if __name__ == '__main__':
    asyncio.run(test())
