param(
  [string]$Repo = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
  [string]$Filename = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
  [string]$OutPath = "..\models\tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
  [switch]$UseCli
)

$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'

$fullOut = Join-Path $PSScriptRoot $OutPath
$dir = Split-Path $fullOut
if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

if ($UseCli) {
  Write-Host "Using hf to download $Repo $Filename"
  hf download $Repo $Filename --local-dir $dir --local-dir-use-symlinks False
  if (Test-Path (Join-Path $dir $Filename)) {
    Write-Host "Model downloaded to $dir/$Filename"
    exit 0
  } else {
    Write-Warning "hf did not produce expected file; falling back to direct URL if provided."
  }
}

Write-Host "Falling back to direct download requires -Repo and -Filename URL; skipping here."
Write-Host "Done."
