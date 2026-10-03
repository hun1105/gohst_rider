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
3. Unity Play → 로봇을 바닥 원점 마커에 놓고 관제 맵에서 클릭 → `P` (위치 원점) — 두 대 각각.
   - 실측 통로(폭 0.445 m(Burger 2.5대) × 길이 2.317 m) 1:1 맵. 원점 마커: 통로 중앙선, 양 끝벽에서 각각 0.41 m 안쪽 (두 마커 간격 1.50 m).
   - TB1은 +Z(앞쪽 끝벽) 방향, TB2는 TB1을 마주 보게 놓는다.
4. 관제 맵에서 로봇 클릭 → God-View로 복귀(`B`/Tab) → `Y`/`R`로 AUTO. 다른 로봇도 같은 방법.
5. 1.0m 만나면 둘 다 정지·적색 → 비켜줄 로봇 클릭(콕핏 진입 = MANUAL) → 후진·회전 → God-View 복귀 → 각각 `Y`/`R` 재개.
