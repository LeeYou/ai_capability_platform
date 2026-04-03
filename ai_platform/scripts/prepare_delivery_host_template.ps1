param(
    [string]$BuildConfig = "Release",
    [string]$BuildBinDir = (Join-Path $PSScriptRoot "..\build\bin\Release"),
    [string]$SourceRoot = (Join-Path $PSScriptRoot ".."),
    [string]$TargetRoot = (Join-Path $PSScriptRoot "..\deploy\host_template"),
    [switch]$CleanTarget
)

$ErrorActionPreference = "Stop"

$resolvedBuildBinDir = [System.IO.Path]::GetFullPath($BuildBinDir)
$resolvedSourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
$resolvedTargetRoot = [System.IO.Path]::GetFullPath($TargetRoot)

$serverExeName = "ai_platform_server.exe"
$pluginDllNames = @(
    "libcap_face_detect.dll",
    "libcap_liveness_action.dll",
    "libcap_idcard_detect.dll",
    "libcap_doc_classify.dll",
    "libcap_seal_detect.dll"
)
$modelDirectories = @(
    "face_detect",
    "liveness_action",
    "idcard_detect",
    "doc_classify",
    "seal_detect"
)

function New-DirectoryIfMissing {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Copy-RequiredFile {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )

    if (-not (Test-Path $SourcePath)) {
        throw ("required file not found: {0}" -f $SourcePath)
    }

    New-DirectoryIfMissing -Path ([System.IO.Path]::GetDirectoryName($TargetPath))
    Copy-Item -Path $SourcePath -Destination $TargetPath -Force
}

function Copy-OptionalDirectory {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )

    if (-not (Test-Path $SourcePath)) {
        Write-Host ("[prepare_delivery_host_template] skip missing directory: {0}" -f $SourcePath)
        return
    }

    if (Test-Path $TargetPath) {
        Remove-Item -Path $TargetPath -Recurse -Force
    }
    Copy-Item -Path $SourcePath -Destination $TargetPath -Recurse -Force
}

function Resolve-ModelDirectorySource {
    param(
        [string]$PrimarySourcePath,
        [string]$FallbackSourcePath
    )

    if (Test-Path $PrimarySourcePath) {
        return $PrimarySourcePath
    }

    if (Test-Path $FallbackSourcePath) {
        return $FallbackSourcePath
    }

    return ""
}

if ($CleanTarget -and (Test-Path $resolvedTargetRoot)) {
    $cleanupPaths = @(
        (Join-Path $resolvedTargetRoot $serverExeName),
        (Join-Path $resolvedTargetRoot "plugins"),
        (Join-Path $resolvedTargetRoot "models"),
        (Join-Path $resolvedTargetRoot "license"),
        (Join-Path $resolvedTargetRoot "logs"),
        (Join-Path $resolvedTargetRoot "scripts")
    )
    foreach ($cleanupPath in $cleanupPaths) {
        if (Test-Path $cleanupPath) {
            Remove-Item -Path $cleanupPath -Recurse -Force
        }
    }
}

New-DirectoryIfMissing -Path $resolvedTargetRoot
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "plugins")
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "models")
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "license")
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "config")
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "logs")
New-DirectoryIfMissing -Path (Join-Path $resolvedTargetRoot "scripts")

Copy-RequiredFile -SourcePath (Join-Path $resolvedBuildBinDir $serverExeName) -TargetPath (Join-Path $resolvedTargetRoot $serverExeName)

foreach ($pluginDllName in $pluginDllNames) {
    Copy-RequiredFile -SourcePath (Join-Path $resolvedBuildBinDir $pluginDllName) -TargetPath (Join-Path $resolvedTargetRoot "plugins\$pluginDllName")
}

Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "config\platform.yaml") -TargetPath (Join-Path $resolvedTargetRoot "config\platform.yaml")
if (-not (Test-Path (Join-Path $resolvedTargetRoot "config\plugins_registry.txt"))) {
    throw ("required delivery registry template not found: {0}" -f (Join-Path $resolvedTargetRoot "config\plugins_registry.txt"))
}
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "config\delivery_acceptance_matrix.json") -TargetPath (Join-Path $resolvedTargetRoot "config\delivery_acceptance_matrix.json")
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "scripts\api_smoke_test.ps1") -TargetPath (Join-Path $resolvedTargetRoot "scripts\api_smoke_test.ps1")
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "scripts\run_platform_smoke.ps1") -TargetPath (Join-Path $resolvedTargetRoot "scripts\run_platform_smoke.ps1")
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "scripts\run_delivery_acceptance.ps1") -TargetPath (Join-Path $resolvedTargetRoot "scripts\run_delivery_acceptance.ps1")
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "scripts\run_delivery_acceptance_matrix.ps1") -TargetPath (Join-Path $resolvedTargetRoot "scripts\run_delivery_acceptance_matrix.ps1")
Copy-RequiredFile -SourcePath (Join-Path $resolvedSourceRoot "scripts\validate_plugins_registry.ps1") -TargetPath (Join-Path $resolvedTargetRoot "scripts\validate_plugins_registry.ps1")

$demoLicenseSource = Join-Path $resolvedSourceRoot "build\tmp\demo_license.dat"
if (Test-Path $demoLicenseSource) {
    Copy-Item -Path $demoLicenseSource -Destination (Join-Path $resolvedTargetRoot "license\license.dat") -Force
}

foreach ($modelDirectory in $modelDirectories) {
    $resolvedModelSource = Resolve-ModelDirectorySource -PrimarySourcePath (Join-Path $resolvedSourceRoot "deploy\host_template\models\$modelDirectory") -FallbackSourcePath (Join-Path $resolvedSourceRoot "models\$modelDirectory")
    Copy-OptionalDirectory -SourcePath $resolvedModelSource -TargetPath (Join-Path $resolvedTargetRoot "models\$modelDirectory")
}

Write-Host ("[prepare_delivery_host_template] build_config={0}" -f $BuildConfig)
Write-Host ("[prepare_delivery_host_template] build_bin_dir={0}" -f $resolvedBuildBinDir)
Write-Host ("[prepare_delivery_host_template] target_root={0}" -f $resolvedTargetRoot)
Write-Host "[prepare_delivery_host_template] delivery host template prepared"
