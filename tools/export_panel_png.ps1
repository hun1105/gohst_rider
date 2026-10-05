# PANEL_B4.pptx -> PANEL_B4.png (이미지 제출용, 3000 x 4250 px). PowerPoint 설치 필요.
# 실행: powershell -ExecutionPolicy Bypass -File tools/export_panel_png.ps1
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "docs\PANEL_B4.pptx"
$dst = Join-Path $root "docs\PANEL_B4.png"
$pp = New-Object -ComObject PowerPoint.Application
try {
  $p = $pp.Presentations.Open($src, $true, $false, $false)
  $p.Slides(1).Export($dst, "PNG", 3000, 4250)
  $p.Close()
  "written $dst"
} finally { $pp.Quit() }
