# setup_agents.ps1 — 에이전트 킷 1회 설치
# 위치: 프로젝트 루트 (ai_relay_server, PhysicalAI_AGV_VR 와 같은 폴더)
# 실행: powershell -ExecutionPolicy Bypass -File setup_agents.ps1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

function Step($n, $msg) { Write-Host "`n[$n/6] $msg" -ForegroundColor Cyan }

# 1. 구조 확인
Step 1 "프로젝트 구조 확인"
foreach ($d in @("ai_relay_server", "PhysicalAI_AGV_VR")) {
    if (-not (Test-Path $d)) { Write-Host "  경고: $d 없음. 프로젝트 루트에서 실행했는지 확인." -ForegroundColor Yellow }
    else { Write-Host "  OK $d" }
}
if ($PSScriptRoot -match "OneDrive") {
    Write-Host "  경고: OneDrive 경로. Unity Library 동기화 충돌 위험 → C:\dev\ 이동 권장." -ForegroundColor Yellow
}

# 2. Python venv
Step 2 "Python 확인 (venv: C:\Users\hun\ai_env)"
$py = "C:\Users\hun\ai_env\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py --version

# 3. 패키지
Step 3 "google-genai, pydantic 설치"
& $py -m pip install -q --upgrade google-genai pydantic

# 4. API 키
Step 4 "GEMINI_API_KEY 확인"
$key = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
if (-not $key) {
    $key = Read-Host "  Google AI Studio API 키 입력 (aistudio.google.com/apikey)"
    [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $key, "User")
    $env:GEMINI_API_KEY = $key
    Write-Host "  사용자 환경변수 저장 완료. 새 터미널부터 자동 적용."
} else { $env:GEMINI_API_KEY = $key; Write-Host "  OK (설정됨)" }

# 5. git
Step 5 "git 초기화 + 에이전트 브랜치"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  git 미설치 → https://git-scm.com 설치 후 재실행." -ForegroundColor Yellow
} else {
    if (-not (Test-Path ".git")) {
        git init -b main | Out-Null
        git add -A
        git commit -m "[human] init: 프로젝트 + 에이전트 킷" | Out-Null
        Write-Host "  git init 완료"
    } else { Write-Host "  기존 저장소 사용" }
    foreach ($b in @("agent/claude", "agent/antigravity")) {
        git show-ref --verify --quiet "refs/heads/$b"
        if ($LASTEXITCODE -ne 0) { git branch $b | Out-Null; Write-Host "  브랜치 생성: $b" }
    }
}

# 6. 워커 동작 테스트
Step 6 "gemini_worker 드라이런 + 실호출 테스트"
& $py tools/gemini_worker.py --dry-run -g "ai_relay_server/*.py" -t "구조"
& $py tools/gemini_worker.py -f AGENTS.md -t "이 프로젝트 에이전트 역할 분담 요약"

Write-Host "`n설치 완료. 다음: README_AGENTS.md '일일 사용법' 참고." -ForegroundColor Green
