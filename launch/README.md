# launch — 실행 스크립트 모음

| 파일 | 용도 |
|---|---|
| `start_tb1_robot.bat` | 실물 TB1 기동 (SSH: roscore + rosbridge + 브링업, ROS 1 Noetic). TB1 고정 IP 172.30.1.58 |
| `start_tb2_robot.bat` | 실물 TB2 기동 (SSH: rosbridge + ustreamer 카메라 + 브링업, ROS 2 Humble) |
| `run_relay_tb1_tb2.bat` | **실물 2대** 릴레이 (tb1=TB1, tb2=TB2·카메라). 두 대 AUTO 시연용 |
| `run_relay_tb2_as_tb1.bat` | 1대 시험: 실물 TB2를 tb1 역할로 (tb2 가상) |
| `run_relay_tb2.bat` | 1대 시험: 실물 TB2만 tb2로 (tb1 가상) |

## 2대 시연 순서
1. `start_tb1_robot.bat`, `start_tb2_robot.bat` 각각 실행 → 브링업 로그 확인 (창 닫지 말 것).
2. `run_relay_tb1_tb2.bat` → `[T-012] tb1 = REAL`, `tb2 = REAL`, `rosbridge connected` 2줄 확인.
3. Unity Play → 두 로봇을 시작 자리에 놓기. 처음 `R`을 누르면 두 대 위치가 시작 자리 기준으로 자동 재설정됨 (중간에 다시 맞추려면 `Shift+P`).
   - 출발 배치: 두 로봇을 마주 보게, 범퍼 사이 Galaxy S20 FE 세로 6개(0.959 m). Unity 시작 위치와 같음.
4. 관제 시점에서 `R`(퀘스트 Y) → 두 대 모두 AUTO. 한 대만 켜려면 그 로봇을 선택한 뒤 `Shift+R`.
5. 0.3m 만나면 둘 다 정지·적색 → 비켜줄 로봇 클릭(콕핏 진입 = MANUAL) → 후진·회전 → God-View 복귀 → 각각 `Y`/`R` 재개.
