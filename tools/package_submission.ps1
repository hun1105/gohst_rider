# package_submission.ps1 — 제4회 경남 AI·SW 경진대회 최종 산출물 패키징 (구글폼 ZIP 1개)
# 사용: powershell -ExecutionPolicy Bypass -File tools/package_submission.ps1 -LeaderName <팀장명> `
#         -ApplicationPath <신청서 최종본> -VideoPath <시연영상.mp4> [-RequireClean]
# 결과: dist/대학부_32_<팀장명>.zip  (공고 규칙: 신청구분_신청분야코드_팀장명.zip)
#   ├─ 1_신청서/                 신청서 최종 수정본 (-ApplicationPath)
#   ├─ 2_완료보고서/             REPORT_5P.docx (표지 제외 5쪽 이내)
#   ├─ 3_기술명세서_소스코드/     TECH_SPEC_1P.docx (1쪽) + source_code.zip (실행 순서 launch/README.md)
#   ├─ 4_시연동영상/             -VideoPath (3분 이내 권장)
#   ├─ 5_발표자료/               PRESENTATION_10SLIDES.pptx (10장 이내)
#   ├─ 별지2_출처AI활용신고서/    SOURCE_AI_DISCLOSURE.docx
#   ├─ 참고자료/                 문서 원본(md), PROTOCOL, 콘티, 자동 시험 기록(evidence)
#   └─ MANIFEST.txt              파일별 SHA256, 커밋 해시, 미충족 항목
param(
    [string]$LeaderName = "",
    [string]$Division = "대학부",
    [string]$FieldCode = "32",
    [string]$ApplicationPath = "",
    [string]$VideoPath = "",
    [int]$MaxZipMB = 200,
    [switch]$RequireClean   # Git 커밋 클린 강제: 미커밋 변경 있으면 중단
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Add-Type -AssemblyName System.IO.Compression.FileSystem

# 한글 파일명·'/' 경로 구분자 보존 (Windows PowerShell 5.1 Compress-Archive는 '\' 기록 문제)
function New-Zip([string]$SourceDir, [string]$ZipPath) {
    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($SourceDir, $ZipPath,
        [System.IO.Compression.CompressionLevel]::Optimal, $false, [System.Text.Encoding]::UTF8)
}

$Problems = @()
if (-not $LeaderName) { $LeaderName = "팀장명"; $Problems += "파일명: -LeaderName 미지정 (대학부_32_팀장명.zip 규칙)" }
$PackageName = "${Division}_${FieldCode}_${LeaderName}"

# 소스 ZIP 제외 규칙. .gitignore가 빠져도 캐시·비밀정보는 반드시 걸러지도록 명시
$CacheDirs = @("Library", "Temp", "obj", "Logs", "Build", "Builds", "UserSettings",
               "__pycache__", ".venv", "venv", "build", "install", "log", ".vs", ".idea", "node_modules")
$ExcludePatterns = @(
    ($CacheDirs | ForEach-Object { "(^|/)$([regex]::Escape($_))/" }) +
    @("^dist/", "^\.agent_cache/", "^docs/handoff/", "^ai_relay_server/logs/",
      "\.(pdf|zip|pt|onnx|apk|aab|pyc|csproj|sln)$", "(^|/)\.env$")
)
# 양식: "API Key, 비밀번호 제거" — 소스에 남으면 미충족 처리
$SecretPatterns = @("sk-[A-Za-z0-9]{20,}", "AIza[0-9A-Za-z_\-]{30,}", "ghp_[A-Za-z0-9]{30,}")
# 실제 비밀번호 문자열은 저장소에 올리지 않음 → git 제외 로컬 파일(한 줄에 하나, 정규식)에서 추가
$LocalSecretFile = Join-Path $PSScriptRoot "secret_patterns.local.txt"
if (Test-Path -LiteralPath $LocalSecretFile) {
    $SecretPatterns += Get-Content -LiteralPath $LocalSecretFile -Encoding UTF8 | Where-Object { $_.Trim() -and -not $_.StartsWith("#") }
} else { Write-Warning "tools/secret_patterns.local.txt 없음 — 기본 패턴(API 키)만 검사" }
# 공란 자리표시 (팀명·팀장명 미기입 검사)
$Placeholders = @("[팀명]", "[팀장명]", "[팀원명]", "[발표자]")

$Deliverables = [ordered]@{
    "2_완료보고서"           = @("docs/REPORT_5P.docx")
    "3_기술명세서_소스코드"   = @("docs/TECH_SPEC_1P.docx")
    "5_발표자료"             = @("docs/PRESENTATION_10SLIDES.pptx")
    "별지2_출처AI활용신고서"  = @("docs/SOURCE_AI_DISCLOSURE.docx")
}
$References = @("docs/REPORT_5P.md", "docs/TECH_SPEC_1P.md", "docs/PRESENTATION_10SLIDES.md",
                "docs/VIDEO_SCRIPT_3MIN.md", "docs/SOURCE_AI_DISCLOSURE.md", "docs/PROTOCOL.md")

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stage = Join-Path $env:TEMP "agv_pkg_$Stamp"          # OneDrive 긴 경로 회피용 스테이징
$PkgDir = Join-Path $Stage "package"
$SrcDir = Join-Path $Stage "source"
New-Item -ItemType Directory -Force $PkgDir, $SrcDir | Out-Null

Write-Host "[1/6] Git 상태 확인"
$Commit = (git rev-parse --short HEAD).Trim()
$Dirty = git status --porcelain
if ($Dirty) {
    $msg = "미커밋 변경 $(@($Dirty).Count)건 — 커밋 후 다시 실행 권장 (MANIFEST 커밋 해시와 소스 불일치)"
    if ($RequireClean) { throw $msg }
    Write-Warning $msg
    $Problems += "소스: $msg"
}

Write-Host "[2/6] 소스 수집·비밀정보 검사"
$Files = git -c core.quotepath=off ls-files -co --exclude-standard |
    Where-Object { $f = $_; -not ($ExcludePatterns | Where-Object { $f -match $_ }) } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
if (-not $Files) { throw "수집된 파일 0개 — git 저장소 루트에서 실행했는지 확인" }
foreach ($f in $Files) {
    $dst = Join-Path $SrcDir $f
    New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $f -Destination $dst
}
$TextExt = '\.(py|cs|md|txt|bat|ps1|sh|json|yaml|yml|js|ino|xml|cfg|ini)$'
$Leaks = foreach ($f in ($Files | Where-Object { $_ -match $TextExt -and $_ -ne 'tools/package_submission.ps1' })) {   # 검사 패턴 자신 제외
    $hit = Select-String -LiteralPath $f -Pattern $SecretPatterns -List -ErrorAction SilentlyContinue
    if ($hit) { "${f}:$($hit.LineNumber)" }
}
if ($Leaks) { $Problems += "소스: 비밀정보 의심 $(@($Leaks).Count)건 → $($Leaks -join ', ')" }
$MissingMeta = $Files | Where-Object { $_ -like "PhysicalAI_AGV_VR/Assets/*.cs" -and -not (Test-Path -LiteralPath "$_.meta") }
if ($MissingMeta) { $Problems += "소스: .meta 누락 $($MissingMeta -join ', ')" }

Write-Host "[3/6] source_code.zip 생성 ($(@($Files).Count)개 파일)"
$SpecDir = New-Item -ItemType Directory -Force (Join-Path $PkgDir "3_기술명세서_소스코드")
New-Zip $SrcDir (Join-Path $SpecDir "source_code.zip")
$SrcMB = [math]::Round((Get-Item (Join-Path $SpecDir "source_code.zip")).Length / 1MB, 1)

Write-Host "[4/6] 제출물 5종 + 별지2 배치"
foreach ($folder in $Deliverables.Keys) {
    $out = New-Item -ItemType Directory -Force (Join-Path $PkgDir $folder)
    foreach ($d in $Deliverables[$folder]) {
        if (Test-Path -LiteralPath $d) { Copy-Item -LiteralPath $d -Destination $out }
        else { $Problems += "${folder}: 파일 없음 ($d) — tools/docs_build에서 npm run all" }
    }
}
$AppDir = New-Item -ItemType Directory -Force (Join-Path $PkgDir "1_신청서")
if ($ApplicationPath -and (Test-Path -LiteralPath $ApplicationPath)) { Copy-Item -LiteralPath $ApplicationPath -Destination $AppDir }
else { $Problems += "1_신청서: -ApplicationPath 미지정 또는 파일 없음 (신청서 최종 수정본)" }
$VidDir = New-Item -ItemType Directory -Force (Join-Path $PkgDir "4_시연동영상")
if ($VideoPath -and (Test-Path -LiteralPath $VideoPath)) {
    if ($VideoPath -notmatch '\.mp4$') { $Problems += "4_시연동영상: MP4 아님 ($VideoPath)" }
    Copy-Item -LiteralPath $VideoPath -Destination $VidDir
} else { $Problems += "4_시연동영상: -VideoPath 미지정 또는 파일 없음 (3분 이내 MP4)" }
$RefDir = New-Item -ItemType Directory -Force (Join-Path $PkgDir "참고자료")
foreach ($r in $References) { if (Test-Path -LiteralPath $r) { Copy-Item -LiteralPath $r -Destination $RefDir } }
if (Test-Path -LiteralPath "docs/assets") { Copy-Item -LiteralPath "docs/assets" -Destination (Join-Path $RefDir "assets") -Recurse }
if (Test-Path -LiteralPath "docs/evidence") { Copy-Item -LiteralPath "docs/evidence" -Destination (Join-Path $RefDir "evidence") -Recurse }
else { $Problems += "참고자료: docs/evidence 없음 — test_real_bridge.py 실행 기록 저장" }

Write-Host "[5/6] 자리표시·문서 검사"
foreach ($md in $References) {
    if (-not (Test-Path -LiteralPath $md)) { continue }
    $left = $Placeholders | Where-Object { (Get-Content -LiteralPath $md -Raw -Encoding UTF8).Contains($_) }
    if ($left) { $Problems += "문서: $md 미기입 자리표시 $($left -join ' ') → 채운 뒤 npm run all" }
}
if (Get-ChildItem "docs/assets" -Filter "placeholder_cap_*" -ErrorAction SilentlyContinue | Where-Object {
        -not (Test-Path (Join-Path "docs/assets" ($_.Name -replace '^placeholder_', '' -replace '\.png$', '.jpg'))) -and
        -not (Test-Path (Join-Path "docs/assets" ($_.Name -replace '^placeholder_', ''))) }) {
    $Problems += "문서: 촬영 캡처(docs/assets/cap_*.jpg) 미삽입 → 보고서·발표에 점선 자리표시 남음"
}

Write-Host "[6/6] MANIFEST·최종 ZIP"
$Manifest = @(
    "Package: $PackageName.zip",
    "Packaged: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Commit: $Commit$(if ($Dirty) { ' (+uncommitted changes)' })",
    "Status: $(if ($Problems) { 'INCOMPLETE' } else { 'READY' })"
) + ($Problems | ForEach-Object { "  - $_" }) + @("", "SHA256  SIZE(bytes)  PATH")
Get-ChildItem $PkgDir -Recurse -File | ForEach-Object {
    $Manifest += "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $($_.Length)  $($_.FullName.Substring($PkgDir.Length + 1))"
}
$Manifest | Out-File -Encoding utf8 (Join-Path $PkgDir "MANIFEST.txt")

New-Item -ItemType Directory -Force (Join-Path $Root "dist") | Out-Null
$FinalZip = Join-Path $Root "dist/$PackageName.zip"
New-Zip $PkgDir $FinalZip
Remove-Item -Recurse -Force $Stage
$ZipMB = [math]::Round((Get-Item $FinalZip).Length / 1MB, 1)
if ($ZipMB -gt $MaxZipMB) { $Problems += "ZIP ${ZipMB}MB > ${MaxZipMB}MB (구글폼 업로드 한도 확인)" }

if ($Problems) {
    Write-Host ""
    Write-Host "제출 기준 미충족 $(@($Problems).Count)건:" -ForegroundColor Red
    $Problems | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "PACKAGE INCOMPLETE -> $FinalZip (${ZipMB}MB, source ${SrcMB}MB)" -ForegroundColor Yellow
} else {
    Write-Host "PACKAGE OK -> $FinalZip (${ZipMB}MB, source ${SrcMB}MB)" -ForegroundColor Green
}
