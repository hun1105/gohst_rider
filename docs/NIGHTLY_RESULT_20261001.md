# 야간 작업 결과 — 2026-10-01

> 보고서·자막 파일은 건드리지 않음. 커밋하지 않음 (아침에 검토 후 커밋).

## T-009 tb3_dynamic_detector 하드코딩 경로 제거
- 신규: `hardware_firmware/tb3_dynamic_detector/tb3_dynamic_detector/paths.py`
  - 지도 폴더 = `$TB3_MAP_DIR` → 없으면 `~/tb3_maps`.
- 수정 (7곳, `/mnt/c/Users/hun/...` 전부 제거):

| 파일 | 변경 |
|---|---|
| `launch/slam_dynamic_frontier_super_manager.launch.py` | `map_path` 기본값 → `map_path('tb3_dynamic_frontier_map')` |
| `tb3_dynamic_detector/map_snapshot_saver.py` | `DEFAULT_MAP_PATH` → `map_path('tb3_map')` |
| `launch/slam_dynamic_all.launch.py` | → `map_path('tb3_dynamic_map')` |
| `launch/slam_dynamic_frontier_explore.launch.py` | → `map_path('tb3_dynamic_frontier_map')` |
| `launch/slam_frontier_explore.launch.py` | → `map_path('tb3_frontier_map')` |
| `launch/slam_map_rviz.launch.py` | → `map_path('tb3_map')` |
| `launch/navigation_saved_map.launch.py` | `MAP_DIRECTORY` → `map_directory()` |

- 검증: `py_compile` 전 파일 OK. `/mnt/c` 잔존 0건.
- 미검증: ROS 2 실기 `colcon build` + `ros2 launch` (Windows에선 불가).
- 주의: 폴더가 git 미추적 → 원본 백업 없음. 커밋 전 diff 불가.

### 로봇/WSL에서 확인
```bash
cd ~/<ws> && colcon build --packages-select tb3_dynamic_detector && source install/setup.bash
export TB3_MAP_DIR=~/tb3_maps          # 생략 시 동일 기본값
ros2 launch tb3_dynamic_detector slam_dynamic_frontier_super_manager.launch.py
# 기존 WSL 경로 유지하려면:
export TB3_MAP_DIR=/mnt/c/Users/hun/Documents/Codex/2026-07-29/new-chat-2/outputs/maps
```
- 기존 저장 지도로 `navigation_saved_map` 쓰려면 위 폴더의 `*.yaml`을 `TB3_MAP_DIR`로 복사하거나 export.

## T-010 `tools/package_submission.ps1` 캐시 제외 강화
- `.gitignore` 의존 + 명시 제외 이중화:
  - 폴더: `Library Temp obj Logs Build(s) UserSettings __pycache__ .venv venv build install log .vs .idea`
  - 확장자: `pdf zip pt onnx apk aab pyc csproj sln`, `.env`
- 수집 0건이면 중단.
- 드라이런: 126개 파일, 0.2MB, 캐시 포함 0건, `paths.py` 포함 확인.

```powershell
powershell -ExecutionPolicy Bypass -File tools/package_submission.ps1 -VideoPath "<영상.mp4>" -TeamName "<팀명>"
```
