# unity_check.ps1 — Unity 배치 모드 컴파일 검증
# 사용: powershell -ExecutionPolicy Bypass -File tools/unity_check.ps1
# 성공: "UNITY_CHECK OK" 한 줄 출력 (Gemini 호출 없음 → 쿼터 절약)
# 실패: 에러 라인만 추출 + Gemini 원인 분석 JSON 출력
# 주의: Unity 에디터가 같은 프로젝트를 열고 있으면 배치 모드 실패 → 에디터 닫고 실행.

param(
    [string]$UnityExe = $env:UNITY_EXE,
    [string]$ProjectPath = (Join-Path $PSScriptRoot "..\PhysicalAI_AGV_VR"),
    [switch]$NoGemini
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root ".agent_cache"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "unity_build.log"

if (-not $UnityExe -or -not (Test-Path $UnityExe)) {
    $cand = Get-ChildItem "C:\Program Files\Unity\Hub\Editor\6000*\Editor\Unity.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1
    if ($cand) { $UnityExe = $cand.FullName }
    else { Write-Output "UNITY_CHECK FAIL: Unity.exe 없음. UNITY_EXE 환경변수 설정 필요."; exit 2 }
}

$ProjectPath = Resolve-Path $ProjectPath
Write-Host "[unity_check] $UnityExe" -ForegroundColor DarkGray
Write-Host "[unity_check] $ProjectPath" -ForegroundColor DarkGray

$proc = Start-Process -FilePath $UnityExe -Wait -PassThru -NoNewWindow -ArgumentList @(
    "-batchmode", "-nographics", "-quit",
    "-projectPath", "`"$ProjectPath`"",
    "-logFile", "`"$Log`""
)

if (-not (Test-Path $Log)) { Write-Output "UNITY_CHECK FAIL: 로그 미생성 (exit $($proc.ExitCode)). 에디터가 열려 있는지 확인."; exit 1 }

$errLines = Select-String -Path $Log -Pattern "error CS\d+|Scripts have compiler errors|Exception:|Aborting batchmode" |
            ForEach-Object { $_.Line.Trim() } | Select-Object -Unique
$warnCount = (Select-String -Path $Log -Pattern "warning CS\d+" | Measure-Object).Count

if ($proc.ExitCode -eq 0 -and -not $errLines) {
    Write-Output "UNITY_CHECK OK (warnings: $warnCount)"
    exit 0
}

Write-Output "UNITY_CHECK FAIL (exit $($proc.ExitCode), errors: $($errLines.Count), warnings: $warnCount)"
$errLines | Select-Object -First 30 | ForEach-Object { Write-Output "  $_" }

if (-not $NoGemini) {
    Push-Location $Root
    try {
        python tools/gemini_worker.py --mode log -f $Log -t "Unity 컴파일/배치 실패의 근본 원인과 수정 위치. 같은 원인은 1건으로."
    } finally { Pop-Location }
}
exit 1
