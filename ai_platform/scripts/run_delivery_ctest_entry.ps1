param(
    [ValidateSet("acceptance", "matrix")]
    [string]$Mode,
    [string]$SourceRoot,
    [string]$BuildConfig = "Release"
)

$ErrorActionPreference = "Stop"
$skipExitCode = 125

if ($env:AI_PLATFORM_RUN_DELIVERY_CTEST -ne "1") {
    Write-Host "[run_delivery_ctest_entry] skipped: set AI_PLATFORM_RUN_DELIVERY_CTEST=1 to enable delivery acceptance tests"
    exit $skipExitCode
}

$resolvedSourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
$resolvedBuildBinDir = Join-Path $resolvedSourceRoot ("build\bin\{0}" -f $BuildConfig)

if ($Mode -eq "acceptance") {
    $scriptPath = Join-Path $resolvedSourceRoot "scripts\run_delivery_acceptance.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -BuildBinDir $resolvedBuildBinDir -PrepareDeliveryRoot -CleanDeliveryRoot -CaptureDiagnostics
    exit $LASTEXITCODE
}

$matrixScriptPath = Join-Path $resolvedSourceRoot "scripts\run_delivery_acceptance_matrix.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $matrixScriptPath -BuildBinDir $resolvedBuildBinDir
exit $LASTEXITCODE
