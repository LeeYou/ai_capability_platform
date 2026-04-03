param(
    [string]$BaseUrl = "http://127.0.0.1:26000",
    [string]$Mode = "normal",
    [string]$AdminToken = "demo-admin-token",
    [int]$AutoReloadWaitSeconds = 0,
    [int]$RepeatCount = 1
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http
$DefaultAdminToken = "demo-admin-token"

if ($RepeatCount -gt 1 -and [string]::IsNullOrEmpty($env:AI_PLATFORM_SMOKE_REPEAT_CHILD)) {
    for ($iteration = 1; $iteration -le $RepeatCount; $iteration++) {
        Write-Host ("[api_smoke_test] iteration {0}/{1}" -f $iteration, $RepeatCount)
        $command = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $PSCommandPath,
            "-BaseUrl", $BaseUrl,
            "-Mode", $Mode,
            "-AdminToken", $AdminToken,
            "-AutoReloadWaitSeconds", $AutoReloadWaitSeconds,
            "-RepeatCount", 1
        )

        $previousRepeatChild = $env:AI_PLATFORM_SMOKE_REPEAT_CHILD
        try {
            $env:AI_PLATFORM_SMOKE_REPEAT_CHILD = "1"
            & powershell @command
            if ($LASTEXITCODE -ne 0) {
                throw ("smoke test iteration failed: {0}/{1}" -f $iteration, $RepeatCount)
            }
        } finally {
            $env:AI_PLATFORM_SMOKE_REPEAT_CHILD = $previousRepeatChild
        }
    }
    return
}

function Invoke-JsonRequest {
    param(
        [string]$Method,
        [string]$Url,
        [string]$Body = "",
        [hashtable]$Headers = @{}
    )

    $requestParams = @{
        UseBasicParsing = $true
        Method = $Method
        Uri = $Url
    }

    if ($Headers.Count -gt 0) {
        $requestParams.Headers = $Headers
    }

    if ($Body -ne "") {
        $requestParams.Body = $Body
        $requestParams.ContentType = "application/json"
    }

    try {
        $response = Invoke-WebRequest @requestParams
    } catch {
        throw ("request failed: {0} {1}`nservice may be unreachable; ensure ai_platform_server is started and {1} is accessible`noriginal error: {2}" -f $Method, $Url, $_.Exception.Message)
    }

    return $response.Content | ConvertFrom-Json
}

function Invoke-TextRequest {
    param(
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{}
    )

    $requestParams = @{
        UseBasicParsing = $true
        Method = $Method
        Uri = $Url
    }

    if ($Headers.Count -gt 0) {
        $requestParams.Headers = $Headers
    }

    try {
        return Invoke-WebRequest @requestParams
    } catch {
        throw ("request failed: {0} {1}`nservice may be unreachable; ensure ai_platform_server is started and {1} is accessible`noriginal error: {2}" -f $Method, $Url, $_.Exception.Message)
    }
}

function Invoke-ErrorJsonRequest {
    param(
        [string]$Method,
        [string]$Url,
        [string]$Body = "",
        [string]$ContentType = "application/json",
        [hashtable]$Headers = @{}
    )

    $handler = New-Object System.Net.Http.HttpClientHandler
    $client = New-Object System.Net.Http.HttpClient($handler)
    $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::new($Method), $Url)

    foreach ($headerKey in $Headers.Keys) {
        [void]$request.Headers.TryAddWithoutValidation($headerKey, [string]$Headers[$headerKey])
    }

    if ($Body -ne "") {
        $request.Content = New-Object System.Net.Http.StringContent($Body, [System.Text.Encoding]::UTF8, $ContentType)
    }

    $response = $client.SendAsync($request).GetAwaiter().GetResult()
    $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    $statusCode = [int]$response.StatusCode

    $request.Dispose()
    $client.Dispose()
    $handler.Dispose()

    return @{
        StatusCode = $statusCode
        Body = ($content | ConvertFrom-Json)
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-CapabilityMetric {
    param(
        [object]$CapabilitiesResponse,
        [string]$CapabilityId
    )

    return $CapabilitiesResponse.data.capabilities | Where-Object { $_.capability_id -eq $CapabilityId } | Select-Object -First 1
}

function Get-PortFromBaseUrl {
    param(
        [string]$Url
    )

    $uri = [System.Uri]$Url
    return $uri.Port
}

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $output = & $FilePath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (("native command failed: " + $FilePath + " " + ($Arguments -join ' ')) + "`n" + ($output | Out-String))
    }
}

function Get-LicenseToolPath {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\build\bin\Release\license_tool.exe"))
}

function Get-CurrentLicensePath {
    $licensePath = [Environment]::GetEnvironmentVariable("AI_PLATFORM_LICENSE_PATH")
    if ([string]::IsNullOrWhiteSpace($licensePath)) {
        return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\build\tmp\demo_license.dat"))
    }
    return $licensePath
}

function New-TempLicensePath {
    param(
        [string]$FileName
    )

    return Join-Path ([System.IO.Path]::GetTempPath()) $FileName
}

function Wait-ForCondition {
    param(
        [scriptblock]$Condition,
        [int]$TimeoutSeconds,
        [string]$Message
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return
        }
        Start-Sleep -Milliseconds 300
    }

    throw $Message
}

$health = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/health"
Assert-True ($health.code -eq 0) "health check failed"
Assert-True ($health.data.port -eq (Get-PortFromBaseUrl -Url $BaseUrl)) "health port does not match BaseUrl"

$testPage = Invoke-TextRequest -Method "GET" -Url "$BaseUrl/test"
Assert-True ($testPage.StatusCode -eq 200) "test page request failed"
Assert-True ($testPage.Content -match "AI Platform Test Page") "test page html not returned"
Assert-True ($testPage.Content -match "allow_test_page=true") "test page allow_test_page state not returned"

$licenseStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
Assert-True ($licenseStatus.code -eq 0) "license status request failed"
Assert-True ($licenseStatus.data.effective_now -eq $true) "license status effective_now not returned"
Assert-True ($licenseStatus.data.in_grace_period -eq $false) "license status in_grace_period not returned"
Assert-True ($licenseStatus.data.expired -eq $false) "license status expired not returned"
Assert-True ($licenseStatus.data.failure_reason -eq "") "license status failure_reason should be empty for valid license"
Assert-True ($licenseStatus.data.failure_detail -eq "") "license status failure_detail should be empty for valid license"
Assert-True ($licenseStatus.data.version -eq "1.0") "license status version not returned"
Assert-True ($licenseStatus.data.customer_id -eq "CUST-DEMO-001") "license status customer_id not returned"
Assert-True ($licenseStatus.data.issued_at -eq "2026-03-01T00:00:00Z") "license status issued_at not returned"
Assert-True ($licenseStatus.data.effective_from -eq "2026-03-01T00:00:00Z") "license status effective_from not returned"
Assert-True ($licenseStatus.data.expires_at -eq "2099-12-31T23:59:59Z") "license status expires_at not returned"
Assert-True ($licenseStatus.data.grace_period_hours -eq 24) "license status grace_period_hours not returned"
Assert-True ($licenseStatus.data.allow_reload -eq $true) "license status allow_reload not returned"
Assert-True ($licenseStatus.data.allow_admin_api -eq $true) "license status allow_admin_api not returned"
Assert-True ($licenseStatus.data.allow_test_page -eq $true) "license status allow_test_page not returned"
Assert-True ($licenseStatus.data.denied_capabilities.Count -eq 0) "license status denied_capabilities not returned"

if ($Mode -eq "license_invalid") {
    $licenseStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
    Assert-True ($licenseStatus.code -eq 0) "license status request failed"
    Assert-True ($licenseStatus.data.valid -eq $false) "license status valid flag not returned"

    $licenseInvalidInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}'
    Assert-True ($licenseInvalidInfer.StatusCode -eq 403) "license invalid infer status code not returned"
    Assert-True ($licenseInvalidInfer.Body.code -eq -402) "license invalid infer code not returned"
    Assert-True ($licenseInvalidInfer.Body.message -eq "license invalid") "license invalid infer message not returned"
    Assert-True ($licenseInvalidInfer.Body.data.license_failure_reason -ne "") "license invalid infer failure reason not returned"
    Assert-True ($licenseInvalidInfer.Body.data.license_failure_detail -ne "") "license invalid infer failure detail not returned"

    $licenseInvalidReloadAll = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
    Assert-True ($licenseInvalidReloadAll.StatusCode -eq 403) "license invalid reload-all status code not returned"
    Assert-True ($licenseInvalidReloadAll.Body.code -eq -302) "license invalid reload-all code not returned"
    Assert-True ($licenseInvalidReloadAll.Body.message -eq "license invalid") "license invalid reload-all message not returned"
    Assert-True ($licenseInvalidReloadAll.Body.data.license_failure_reason -ne "") "license invalid reload-all failure reason not returned"
    Assert-True ($licenseInvalidReloadAll.Body.data.license_failure_detail -ne "") "license invalid reload-all failure detail not returned"

    $licenseInvalidReloadSingle = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
    Assert-True ($licenseInvalidReloadSingle.StatusCode -eq 403) "license invalid reload status code not returned"
    Assert-True ($licenseInvalidReloadSingle.Body.code -eq -302) "license invalid reload code not returned"
    Assert-True ($licenseInvalidReloadSingle.Body.message -eq "license invalid") "license invalid reload message not returned"
    Assert-True ($licenseInvalidReloadSingle.Body.data.license_failure_reason -ne "") "license invalid reload failure reason not returned"
    Assert-True ($licenseInvalidReloadSingle.Body.data.license_failure_detail -ne "") "license invalid reload failure detail not returned"

    Write-Host "api smoke test passed"
    return
}

$invalidJsonInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{'
Assert-True ($invalidJsonInfer.StatusCode -eq 400) "invalid json infer status code not returned"
Assert-True ($invalidJsonInfer.Body.code -eq -400) "invalid json infer code not returned"
Assert-True ($invalidJsonInfer.Body.message -eq "invalid json body") "invalid json infer message not returned"

$invalidContentTypeInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}' -ContentType "text/plain"
Assert-True ($invalidContentTypeInfer.StatusCode -eq 400) "invalid content-type infer status code not returned"
Assert-True ($invalidContentTypeInfer.Body.code -eq -400) "invalid content-type infer code not returned"
Assert-True ($invalidContentTypeInfer.Body.message -eq "content-type must be application/json") "invalid content-type infer message not returned"

$missingMediaInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"params":{"threshold":0.5}}'
Assert-True ($missingMediaInfer.StatusCode -eq 400) "missing media infer status code not returned"
Assert-True ($missingMediaInfer.Body.code -eq -400) "missing media infer code not returned"
Assert-True ($missingMediaInfer.Body.message -eq "missing media input") "missing media infer message not returned"

$emptyImagesInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[]}'
Assert-True ($emptyImagesInfer.StatusCode -eq 400) "empty images infer status code not returned"
Assert-True ($emptyImagesInfer.Body.code -eq -400) "empty images infer code not returned"
Assert-True ($emptyImagesInfer.Body.message -eq "images array is empty") "empty images infer message not returned"

$longRequestId = ('a' * 129)
$longRequestIdInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body ('{"request_id":"' + $longRequestId + '","images":[{"uri":"demo.jpg"}]}')
Assert-True ($longRequestIdInfer.StatusCode -eq 400) "long request_id infer status code not returned"
Assert-True ($longRequestIdInfer.Body.code -eq -400) "long request_id infer code not returned"
Assert-True ($longRequestIdInfer.Body.message -eq "request_id too long") "long request_id infer message not returned"

$invalidImagesInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":{}}'
Assert-True ($invalidImagesInfer.StatusCode -eq 400) "invalid images infer status code not returned"
Assert-True ($invalidImagesInfer.Body.code -eq -400) "invalid images infer code not returned"
Assert-True ($invalidImagesInfer.Body.message -eq "invalid images") "invalid images infer message not returned"

$unsupportedImageFormatInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"data":"YWJjZA==","format":"gif"}]}'
Assert-True ($unsupportedImageFormatInfer.StatusCode -eq 400) "unsupported image format infer status code not returned"
Assert-True ($unsupportedImageFormatInfer.Body.code -eq -400) "unsupported image format infer code not returned"
Assert-True ($unsupportedImageFormatInfer.Body.message -eq "unsupported image format") "unsupported image format infer message not returned"

$invalidImageDataInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"data":"not-base64","format":"jpg"}]}'
Assert-True ($invalidImageDataInfer.StatusCode -eq 400) "invalid image data status code not returned"
Assert-True ($invalidImageDataInfer.Body.code -eq -400) "invalid image data code not returned"
Assert-True ($invalidImageDataInfer.Body.message -eq "invalid image data") "invalid image data message not returned"

$invalidImageUriInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"https://example.com/demo.jpg","format":"jpg"}]}'
Assert-True ($invalidImageUriInfer.StatusCode -eq 400) "invalid image uri status code not returned"
Assert-True ($invalidImageUriInfer.Body.code -eq -400) "invalid image uri code not returned"
Assert-True ($invalidImageUriInfer.Body.message -eq "invalid image uri") "invalid image uri message not returned"

$unsupportedMediaFormatInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"media":{"type":"video","data":"YWJjZA==","format":"wmv"}}'
Assert-True ($unsupportedMediaFormatInfer.StatusCode -eq 400) "unsupported media format infer status code not returned"
Assert-True ($unsupportedMediaFormatInfer.Body.code -eq -400) "unsupported media format infer code not returned"
Assert-True ($unsupportedMediaFormatInfer.Body.message -eq "unsupported media format") "unsupported media format infer message not returned"

$invalidMediaDataInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/liveness_action" -Body '{"media":{"type":"video","data":"not-base64","format":"mp4"},"params":{"action":"blink"}}'
Assert-True ($invalidMediaDataInfer.StatusCode -eq 400) "invalid media data status code not returned"
Assert-True ($invalidMediaDataInfer.Body.code -eq -400) "invalid media data code not returned"
Assert-True ($invalidMediaDataInfer.Body.message -eq "invalid media data") "invalid media data message not returned"

$invalidMediaUriInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/liveness_action" -Body '{"media":{"type":"video","uri":"https://example.com/demo.mp4","format":"mp4"},"params":{"action":"blink"}}'
Assert-True ($invalidMediaUriInfer.StatusCode -eq 400) "invalid media uri status code not returned"
Assert-True ($invalidMediaUriInfer.Body.code -eq -400) "invalid media uri code not returned"
Assert-True ($invalidMediaUriInfer.Body.message -eq "invalid media uri") "invalid media uri message not returned"

$invalidLivenessActionInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/liveness_action" -Body '{"images":[{"data":"ZnJhbWUx","format":"jpg"},{"data":"ZnJhbWUy","format":"jpg"}],"params":{"action":"wave"}}'
Assert-True ($invalidLivenessActionInfer.StatusCode -eq 400) "invalid liveness action status code not returned"
Assert-True ($invalidLivenessActionInfer.Body.code -eq -400) "invalid liveness action code not returned"
Assert-True ($invalidLivenessActionInfer.Body.message -eq "unsupported liveness action") "invalid liveness action message not returned"

$capabilitiesBefore = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/capabilities"
Assert-True ($capabilitiesBefore.code -eq 0) "capabilities request failed"
$faceCapabilityBefore = Get-CapabilityMetric -CapabilitiesResponse $capabilitiesBefore -CapabilityId "face_detect"
Assert-True ($null -ne $faceCapabilityBefore) "face_detect capability missing"
$livenessCapabilityBefore = Get-CapabilityMetric -CapabilitiesResponse $capabilitiesBefore -CapabilityId "liveness_action"
Assert-True ($null -ne $livenessCapabilityBefore) "liveness_action capability missing"

$rollbackSingleFailureResponse = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/rollback/liveness_action" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($rollbackSingleFailureResponse.StatusCode -eq 400) "rollback single failure status code not returned"
Assert-True ($rollbackSingleFailureResponse.Body.code -eq -308) "rollback single failure code not returned"
Assert-True ($rollbackSingleFailureResponse.Body.data.rollback_performed -eq $false) "rollback single failure rollback_performed should be false"
Assert-True ($rollbackSingleFailureResponse.Body.data.rollback_reason -eq "previous_model_dir_unavailable") "rollback single failure rollback_reason not returned"
Assert-True ($rollbackSingleFailureResponse.Body.data.rollback_failed_stage -eq "prepare") "rollback single failure rollback_failed_stage not returned"

$rollbackAllFailureResponse = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/rollback-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($rollbackAllFailureResponse.StatusCode -eq 400) "rollback-all failure status code not returned"
Assert-True ($rollbackAllFailureResponse.Body.code -eq -309) "rollback-all failure code not returned"
Assert-True ($rollbackAllFailureResponse.Body.data.rollback_all -eq $true) "rollback-all failure rollback_all not returned"
Assert-True (($rollbackAllFailureResponse.Body.data.rollback_performed -eq $true) -or ($rollbackAllFailureResponse.Body.data.rollback_performed -eq $false)) "rollback-all failure rollback_performed not returned"
Assert-True ($rollbackAllFailureResponse.Body.data.rollback_reason -eq "previous_model_dir_unavailable") "rollback-all failure rollback_reason not returned"
Assert-True ($rollbackAllFailureResponse.Body.data.rollback_failed_stage -eq "prepare") "rollback-all failure rollback_failed_stage not returned"
Assert-True ($rollbackAllFailureResponse.Body.data.rollback_failure_details.Count -ge 1) "rollback-all failure rollback_failure_details not returned"
$idcardRollbackFailureDetail = $rollbackAllFailureResponse.Body.data.rollback_failure_details | Where-Object { $_.capability_id -eq "idcard_detect" } | Select-Object -First 1
Assert-True ($null -ne $idcardRollbackFailureDetail) "rollback-all failure detail for a non-reloaded capability not returned"
Assert-True ($idcardRollbackFailureDetail.rollback_reason -eq "previous_model_dir_unavailable") "rollback-all failure detail rollback_reason not returned"

$successInfer = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($successInfer.code -eq 0) "success infer request failed"

$videoInfer = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/liveness_action" -Body '{"media":{"type":"video","data":"dmlkZW8tZGVtbw==","format":"mp4"},"params":{"action":"blink"}}'
Assert-True ($videoInfer.code -eq 0) "video infer request failed"
Assert-True ($videoInfer.data.is_live -eq $true) "video infer is_live not returned"
Assert-True ($videoInfer.data.mock -eq $true) "video infer mock flag not returned"
Assert-True ($videoInfer.data.input_summary.media_type -eq "video") "video infer media_type not returned"
Assert-True ($videoInfer.data.input_summary.media_format -eq "mp4") "video infer media_format not returned"
Assert-True ($videoInfer.data.input_summary.action -eq "blink") "video infer action not returned"

$frameSequenceInfer = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/liveness_action" -Body '{"images":[{"data":"ZnJhbWUx","format":"jpg"},{"data":"ZnJhbWUy","format":"jpg"}],"params":{"action":"nod"}}'
Assert-True ($frameSequenceInfer.code -eq 0) "frame sequence infer request failed"
Assert-True ($frameSequenceInfer.data.is_live -eq $true) "frame sequence infer is_live not returned"
Assert-True ($frameSequenceInfer.data.input_summary.media_type -eq "frame_sequence") "frame sequence media_type not returned"
Assert-True ($frameSequenceInfer.data.input_summary.image_count -eq 2) "frame sequence image_count not returned"

$licenseToolPath = Get-LicenseToolPath
$activeLicensePath = Get-CurrentLicensePath
$licenseBackupPath = New-TempLicensePath -FileName "demo_license_backup_for_reload_test.dat"
$restrictedLicensePath = New-TempLicensePath -FileName "demo_license_restricted_for_reload_test.dat"

Copy-Item -Path $activeLicensePath -Destination $licenseBackupPath -Force
Invoke-NativeCommand -FilePath $licenseToolPath -Arguments @(
    "generate",
    $restrictedLicensePath,
    "demo_customer",
    "face_detect,liveness_action,not_exist_cap",
    "--denied-capabilities",
    "face_detect",
    "--allow-reload",
    "false",
    "--allow-admin-api",
    "true",
    "--allow-test-page",
    "false"
)

Copy-Item -Path $restrictedLicensePath -Destination $activeLicensePath -Force
$restrictedReload = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($restrictedReload.code -eq 0) "restricted license reload request failed"
Assert-True ($restrictedReload.data.reloaded -eq $true) "restricted license reload flag not returned"
Assert-True ($restrictedReload.data.allow_admin_api -eq $true) "restricted license allow_admin_api not returned"
Assert-True ($restrictedReload.data.allow_reload -eq $false) "restricted license allow_reload not applied"

$restrictedStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
Assert-True ($restrictedStatus.data.valid -eq $true) "restricted license should remain valid"
Assert-True ($restrictedStatus.data.allow_admin_api -eq $true) "restricted status allow_admin_api not updated"
Assert-True ($restrictedStatus.data.allow_reload -eq $false) "restricted status allow_reload not updated"
Assert-True ($restrictedStatus.data.allow_test_page -eq $false) "restricted status allow_test_page not updated"
Assert-True ($restrictedStatus.data.denied_capabilities.Count -eq 1) "restricted denied_capabilities count not updated"
Assert-True ($restrictedStatus.data.denied_capabilities[0] -eq "face_detect") "restricted denied_capabilities content not updated"

$restrictedFaceInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($restrictedFaceInfer.StatusCode -eq 403) "restricted face_detect infer status code not returned"
Assert-True ($restrictedFaceInfer.Body.code -eq -401) "restricted face_detect infer code not returned"
Assert-True ($restrictedFaceInfer.Body.message -eq "capability not licensed") "restricted face_detect infer message not returned"

$restrictedReloadAll = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($restrictedReloadAll.StatusCode -eq 403) "restricted reload-all status code not returned"
Assert-True ($restrictedReloadAll.Body.code -eq -305) "restricted reload-all code not returned"
Assert-True ($restrictedReloadAll.Body.message -eq "reload disabled by license") "restricted reload-all message not returned"

$restrictedReloadSingle = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($restrictedReloadSingle.StatusCode -eq 403) "restricted reload single status code not returned"
Assert-True ($restrictedReloadSingle.Body.code -eq -305) "restricted reload single code not returned"
Assert-True ($restrictedReloadSingle.Body.message -eq "reload disabled by license") "restricted reload single message not returned"

$restrictedTestPage = Invoke-ErrorJsonRequest -Method "GET" -Url "$BaseUrl/test"
Assert-True ($restrictedTestPage.StatusCode -eq 403) "restricted test page status code not returned"
Assert-True ($restrictedTestPage.Body.code -eq -307) "restricted test page code not returned"
Assert-True ($restrictedTestPage.Body.message -eq "test page disabled by license") "restricted test page message not returned"

Copy-Item -Path $licenseBackupPath -Destination $activeLicensePath -Force
$restoreReload = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($restoreReload.code -eq 0) "restore license reload request failed"
Assert-True ($restoreReload.data.allow_reload -eq $true) "restore license allow_reload not recovered"

$restoredStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
Assert-True ($restoredStatus.data.valid -eq $true) "restored license should remain valid"
Assert-True ($restoredStatus.data.allow_reload -eq $true) "restored status allow_reload not recovered"
Assert-True ($restoredStatus.data.allow_admin_api -eq $true) "restored status allow_admin_api not recovered"
Assert-True ($restoredStatus.data.allow_test_page -eq $true) "restored status allow_test_page not recovered"
Assert-True ($restoredStatus.data.denied_capabilities.Count -eq 0) "restored denied_capabilities not recovered"

$restoredTestPage = Invoke-TextRequest -Method "GET" -Url "$BaseUrl/test"
Assert-True ($restoredTestPage.StatusCode -eq 200) "restored test page request failed"
Assert-True ($restoredTestPage.Content -match "allow_test_page=true") "restored test page allow_test_page state not recovered"

$restoredFaceInfer = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($restoredFaceInfer.code -eq 0) "restored face_detect infer request failed"

if ($AutoReloadWaitSeconds -gt 0) {
    Copy-Item -Path $restrictedLicensePath -Destination $activeLicensePath -Force
    Wait-ForCondition -TimeoutSeconds $AutoReloadWaitSeconds -Message "auto reload did not apply restricted license in time" -Condition {
        $status = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
        return ($status.data.allow_reload -eq $false) -and ($status.data.allow_test_page -eq $false)
    }

    $autoRestrictedStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
    Assert-True ($autoRestrictedStatus.data.allow_reload -eq $false) "auto reloaded restricted allow_reload not applied"
    Assert-True ($autoRestrictedStatus.data.allow_test_page -eq $false) "auto reloaded restricted allow_test_page not applied"

    $autoRestrictedTestPage = Invoke-ErrorJsonRequest -Method "GET" -Url "$BaseUrl/test"
    Assert-True ($autoRestrictedTestPage.StatusCode -eq 403) "auto reloaded restricted test page status code not returned"
    Assert-True ($autoRestrictedTestPage.Body.code -eq -307) "auto reloaded restricted test page code not returned"

    Copy-Item -Path $licenseBackupPath -Destination $activeLicensePath -Force
    Wait-ForCondition -TimeoutSeconds $AutoReloadWaitSeconds -Message "auto reload did not restore original license in time" -Condition {
        $status = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
        return ($status.data.allow_reload -eq $true) -and ($status.data.allow_test_page -eq $true)
    }

    $autoRestoredStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
    Assert-True ($autoRestoredStatus.data.allow_reload -eq $true) "auto reloaded restored allow_reload not recovered"
    Assert-True ($autoRestoredStatus.data.allow_test_page -eq $true) "auto reloaded restored allow_test_page not recovered"
}

$invalidLicensePath = New-TempLicensePath -FileName "demo_license_invalid_for_reload_test.dat"
Invoke-NativeCommand -FilePath $licenseToolPath -Arguments @(
    "generate",
    $invalidLicensePath,
    "demo_customer",
    "face_detect,liveness_action,not_exist_cap"
)
$invalidLicenseContent = Get-Content -Path $invalidLicensePath -Raw
$invalidLicenseContent = $invalidLicenseContent -replace "(?s)---SIGNATURE---.*$", "---SIGNATURE---`r`ninvalid-signature`r`n"
Set-Content -Path $invalidLicensePath -Value $invalidLicenseContent -NoNewline

Copy-Item -Path $invalidLicensePath -Destination $activeLicensePath -Force
$failedReload = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($failedReload.StatusCode -eq 403) "invalid license reload status code not returned"
Assert-True ($failedReload.Body.code -eq -306) "invalid license reload code not returned"
Assert-True ($failedReload.Body.message -eq "license reload failed") "invalid license reload message not returned"
Assert-True ($failedReload.Body.data.license_failure_reason -eq "signature_invalid") "invalid license reload failure reason not returned"
Assert-True ($failedReload.Body.data.license_failure_detail -eq "license signature invalid") "invalid license reload failure detail not returned"

$statusAfterFailedReload = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/status"
Assert-True ($statusAfterFailedReload.data.valid -eq $true) "status should keep previous valid license after failed reload"
Assert-True ($statusAfterFailedReload.data.allow_reload -eq $true) "status allow_reload should keep previous value after failed reload"
Assert-True ($statusAfterFailedReload.data.denied_capabilities.Count -eq 0) "status denied_capabilities should keep previous value after failed reload"

$inferAfterFailedReload = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_detect" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($inferAfterFailedReload.code -eq 0) "infer should keep working after failed reload"

Copy-Item -Path $licenseBackupPath -Destination $activeLicensePath -Force

$reloadSingleFailureResponse = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{"type":"model","target_model_dir":"__test_fail_reload__:face_detect"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadSingleFailureResponse.StatusCode -eq 400) "reload single failure status code not returned"
Assert-True ($reloadSingleFailureResponse.Body.code -eq -300) "reload single failure code not returned"
Assert-True ($reloadSingleFailureResponse.Body.message -eq "plugin reload returned non-zero") "reload single failure message not returned"

$reloadAllFailureResponse = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{"type":"model","target_model_dir":"__test_fail_reload__:face_detect"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadAllFailureResponse.StatusCode -eq 400) "reload-all failure status code not returned"
Assert-True ($reloadAllFailureResponse.Body.code -eq -301) "reload-all failure code not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reloaded_all -eq $true) "reload-all failure reloaded_all not returned"
Assert-True ($reloadAllFailureResponse.Body.data.rolled_back -eq $true) "reload-all failure rolled_back not returned"
Assert-True ($reloadAllFailureResponse.Body.data.restored_previous_state -eq $true) "reload-all failure restored_previous_state not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reloaded_capability_ids.Count -ge 1) "reload-all failure reloaded_capability_ids not returned"
Assert-True ($reloadAllFailureResponse.Body.data.failed_capability_ids.Count -eq 1) "reload-all failure failed_capability_ids not returned"
Assert-True ($reloadAllFailureResponse.Body.data.failed_capability_ids[0] -eq "face_detect") "reload-all failure failed capability id not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reload_failure_details.Count -eq 1) "reload-all failure reload_failure_details not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reload_failure_details[0].capability_id -eq "face_detect") "reload-all failure detail capability_id not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reload_failure_details[0].reload_reason -eq "reload_failed") "reload-all failure detail reload_reason not returned"
Assert-True ($reloadAllFailureResponse.Body.data.reload_failure_details[0].reload_failed_stage -eq "reload") "reload-all failure detail reload_failed_stage not returned"

$reloadAllResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadAllResponse.code -eq 0) "reload-all request failed"
Assert-True ($reloadAllResponse.data.reloaded_all -eq $true) "reload-all response flag not returned"
Assert-True ($reloadAllResponse.data.reload_type -eq "all") "reload-all default reload_type not returned"
Assert-True ($reloadAllResponse.data.reloaded_capability_ids.Count -ge 1) "reload-all response reloaded_capability_ids not returned"
Assert-True ($reloadAllResponse.data.failed_capability_ids.Count -eq 0) "reload-all response failed_capability_ids should be empty"
Assert-True ($reloadAllResponse.data.reload_failure_details.Count -eq 0) "reload-all response reload_failure_details should be empty"

$reloadSingleResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadSingleResponse.code -eq 0) "reload single request failed"
Assert-True ($reloadSingleResponse.data.reloaded -eq $true) "reload single response flag not returned"
Assert-True ($reloadSingleResponse.data.reload_type -eq "all") "reload single default reload_type not returned"
Assert-True ($frameSequenceInfer.data.input_summary.action -eq "nod") "frame sequence action not returned"

$reloadAllModelResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{"type":"model"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadAllModelResponse.code -eq 0) "reload-all model request failed"
Assert-True ($reloadAllModelResponse.data.reloaded_all -eq $true) "reload-all model response flag not returned"
Assert-True ($reloadAllModelResponse.data.reload_type -eq "model") "reload-all model reload_type not returned"
Assert-True ($null -ne $reloadAllModelResponse.data.previous_model_dir) "reload-all model previous_model_dir not returned"
Assert-True ($null -ne $reloadAllModelResponse.data.current_model_dir) "reload-all model current_model_dir not returned"
Assert-True ($reloadAllModelResponse.data.target_model_dir -eq "") "reload-all model default target_model_dir not returned"
Assert-True ($reloadAllModelResponse.data.reload_failure_details.Count -eq 0) "reload-all model reload_failure_details should be empty"

$reloadSinglePluginResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{"type":"plugin"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadSinglePluginResponse.code -eq 0) "reload single plugin request failed"
Assert-True ($reloadSinglePluginResponse.data.reloaded -eq $true) "reload single plugin response flag not returned"
Assert-True ($reloadSinglePluginResponse.data.reload_type -eq "plugin") "reload single plugin reload_type not returned"
Assert-True ($null -ne $reloadSinglePluginResponse.data.previous_model_dir) "reload single plugin previous_model_dir not returned"
Assert-True ($null -ne $reloadSinglePluginResponse.data.current_model_dir) "reload single plugin current_model_dir not returned"
Assert-True ($reloadSinglePluginResponse.data.target_model_dir -eq "") "reload single plugin target_model_dir should be empty"

$reloadSingleModelTargetResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{"type":"model","target_model_dir":"models/face_detect/v2"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadSingleModelTargetResponse.code -eq 0) "reload single model target request failed"
Assert-True ($reloadSingleModelTargetResponse.data.reloaded -eq $true) "reload single model target response flag not returned"
Assert-True ($reloadSingleModelTargetResponse.data.reload_type -eq "model") "reload single model target reload_type not returned"
Assert-True ($reloadSingleModelTargetResponse.data.rollback_performed -eq $false) "reload single model target rollback_performed should be false"
Assert-True ($null -ne $reloadSingleModelTargetResponse.data.previous_model_dir) "reload single model target previous_model_dir not returned"
Assert-True ($reloadSingleModelTargetResponse.data.current_model_dir -eq "models/face_detect/v2") "reload single model target current_model_dir not returned"
Assert-True ($reloadSingleModelTargetResponse.data.target_model_dir -eq "models/face_detect/v2") "reload single model target_model_dir not returned"

$reloadLivenessModelTargetResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/liveness_action" -Body '{"type":"model","target_model_dir":"models/liveness_action/v2"}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadLivenessModelTargetResponse.code -eq 0) "reload liveness model target request failed"
Assert-True ($reloadLivenessModelTargetResponse.data.current_model_dir -eq "models/liveness_action/v2") "reload liveness model target current_model_dir not returned"

$rollbackSingleResponse = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/rollback/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($rollbackSingleResponse.code -eq 0) "rollback single request failed"
Assert-True ($rollbackSingleResponse.data.rolled_back -eq $true) "rollback single response flag not returned"
Assert-True ($rollbackSingleResponse.data.reload_type -eq "model") "rollback single reload_type not returned"
Assert-True ($rollbackSingleResponse.data.rollback_performed -eq $true) "rollback single rollback_performed not returned"
Assert-True ($rollbackSingleResponse.data.rollback_source_model_dir -eq "models/face_detect/v2") "rollback single rollback_source_model_dir not returned"
Assert-True ($rollbackSingleResponse.data.rollback_target_model_dir -eq "models/face_detect") "rollback single rollback_target_model_dir not returned"
Assert-True ($rollbackSingleResponse.data.target_model_dir -eq "models/face_detect") "rollback single target_model_dir not returned"
Assert-True ($rollbackSingleResponse.data.current_model_dir -eq "models/face_detect") "rollback single current_model_dir not returned"
Assert-True ($rollbackSingleResponse.data.model_dir -eq "models/face_detect") "rollback single model_dir not returned"

$rollbackAllResponse = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/rollback-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True (($rollbackAllResponse.StatusCode -eq 200) -or ($rollbackAllResponse.StatusCode -eq 400)) "rollback-all response status code not returned"
Assert-True ($rollbackAllResponse.Body.data.rollback_all -eq $true) "rollback-all response rollback_all not returned"
Assert-True ($rollbackAllResponse.Body.data.rollback_performed -eq $true) "rollback-all response rollback_performed not returned"
Assert-True ($rollbackAllResponse.Body.data.rolled_back -eq $true) "rollback-all response rolled_back not returned"
Assert-True ($rollbackAllResponse.Body.data.rolled_back_capability_ids.Count -ge 1) "rollback-all response rolled_back_capability_ids not returned"
if ($rollbackAllResponse.StatusCode -eq 200) {
    Assert-True ($rollbackAllResponse.Body.code -eq 0) "rollback-all success code not returned"
    Assert-True ($rollbackAllResponse.Body.data.restored_previous_state -eq $true) "rollback-all success restored_previous_state not returned"
    Assert-True ($rollbackAllResponse.Body.data.failed_capability_ids.Count -eq 0) "rollback-all success failed_capability_ids should be empty"
    Assert-True ($rollbackAllResponse.Body.data.rollback_failure_details.Count -eq 0) "rollback-all success rollback_failure_details should be empty"
} else {
    Assert-True ($rollbackAllResponse.Body.code -eq -309) "rollback-all partial failure code not returned"
    Assert-True ($rollbackAllResponse.Body.data.restored_previous_state -eq $false) "rollback-all partial failure restored_previous_state not returned"
    Assert-True ($rollbackAllResponse.Body.data.failed_capability_ids.Count -ge 1) "rollback-all partial failure failed_capability_ids not returned"
    Assert-True ($rollbackAllResponse.Body.data.rollback_failure_details.Count -ge 1) "rollback-all partial failure rollback_failure_details not returned"
}

$failureInfer = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/not_exist_cap" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($failureInfer.code -eq -200) "failure infer request did not return expected error code"

$unlicensedInfer = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/infer/face_recognize" -Body '{"images":[{"uri":"demo.jpg"}]}'
Assert-True ($unlicensedInfer.StatusCode -eq 403) "unlicensed infer status code not returned"
Assert-True ($unlicensedInfer.Body.code -eq -401) "unlicensed infer code not returned"
Assert-True ($unlicensedInfer.Body.message -eq "capability not licensed") "unlicensed infer message not returned"

$runtimeMetrics = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/metrics/runtime"
Assert-True ($runtimeMetrics.code -eq 0) "runtime metrics request failed"
$faceMetric = $runtimeMetrics.data.capabilities | Where-Object { $_.capability_id -eq "face_detect" } | Select-Object -First 1
$livenessMetric = $runtimeMetrics.data.capabilities | Where-Object { $_.capability_id -eq "liveness_action" } | Select-Object -First 1
$missingMetric = $runtimeMetrics.data.capabilities | Where-Object { $_.capability_id -eq "not_exist_cap" } | Select-Object -First 1
Assert-True ($null -ne $faceMetric) "face_detect metrics missing"
Assert-True ($null -ne $livenessMetric) "liveness_action metrics missing"
Assert-True ($null -ne $missingMetric) "not_exist_cap metrics missing"
Assert-True ($faceMetric.success_count -ge 1) "face_detect success_count not updated"
Assert-True ($livenessMetric.success_count -ge 1) "liveness_action success_count not updated"
Assert-True ($faceMetric.last_success_timestamp -gt 0) "face_detect last_success_timestamp not updated"
Assert-True ($livenessMetric.last_success_timestamp -gt 0) "liveness_action last_success_timestamp not updated"
Assert-True ($missingMetric.failure_count -ge 1) "not_exist_cap failure_count not updated"
Assert-True ($missingMetric.last_failure_timestamp -gt 0) "not_exist_cap last_failure_timestamp not updated"
Assert-True ($missingMetric.last_error_code -eq -200) "not_exist_cap last_error_code not updated"

$runtimeMetricsMethodNotAllowed = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/metrics/runtime" -Body '{}'
Assert-True ($runtimeMetricsMethodNotAllowed.StatusCode -eq 405) "runtime metrics 405 status code not returned"
Assert-True ($runtimeMetricsMethodNotAllowed.Body.code -eq -405) "runtime metrics 405 body code not returned"
Assert-True ($runtimeMetricsMethodNotAllowed.Body.allow -eq "GET") "runtime metrics allow method not returned"

$reloadAllMissingToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}'
Assert-True ($reloadAllMissingToken.StatusCode -eq 401) "reload all missing token status code not returned"
Assert-True ($reloadAllMissingToken.Body.code -eq -303) "reload all missing token code not returned"
Assert-True ($reloadAllMissingToken.Body.message -eq "admin token invalid") "reload all missing token message not returned"

$reloadAllInvalidToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = "wrong-token" }
Assert-True ($reloadAllInvalidToken.StatusCode -eq 401) "reload all invalid token status code not returned"
Assert-True ($reloadAllInvalidToken.Body.code -eq -303) "reload all invalid token code not returned"
Assert-True ($reloadAllInvalidToken.Body.message -eq "admin token invalid") "reload all invalid token message not returned"

if ($AdminToken -ne $DefaultAdminToken) {
    $reloadAllDefaultToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = $DefaultAdminToken }
    Assert-True ($reloadAllDefaultToken.StatusCode -eq 401) "reload all default token should be invalid when custom admin token is configured"
    Assert-True ($reloadAllDefaultToken.Body.code -eq -303) "reload all default token invalid code not returned"

    $licenseReloadDefaultToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = $DefaultAdminToken }
    Assert-True ($licenseReloadDefaultToken.StatusCode -eq 401) "license reload default token should be invalid when custom admin token is configured"
    Assert-True ($licenseReloadDefaultToken.Body.code -eq -303) "license reload default token invalid code not returned"
}

$licenseReloadMissingToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}'
Assert-True ($licenseReloadMissingToken.StatusCode -eq 401) "license reload missing token status code not returned"
Assert-True ($licenseReloadMissingToken.Body.code -eq -303) "license reload missing token code not returned"
Assert-True ($licenseReloadMissingToken.Body.message -eq "admin token invalid") "license reload missing token message not returned"

$licenseReloadInvalidToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = "wrong-token" }
Assert-True ($licenseReloadInvalidToken.StatusCode -eq 401) "license reload invalid token status code not returned"
Assert-True ($licenseReloadInvalidToken.Body.code -eq -303) "license reload invalid token code not returned"
Assert-True ($licenseReloadInvalidToken.Body.message -eq "admin token invalid") "license reload invalid token message not returned"

$licenseReload = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/license/reload" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($licenseReload.code -eq 0) "license reload request failed"
Assert-True ($licenseReload.data.reloaded -eq $true) "license reload result not returned"
Assert-True ($licenseReload.data.valid -eq $true) "license reload valid flag not returned"

$reloadAll = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload-all" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadAll.code -eq 0) "reload all request failed"
Assert-True ($reloadAll.data.reloaded_all -eq $true) "reload all result not returned"
Assert-True ($reloadAll.data.capability_count -ge 1) "reload all capability_count not returned"

$reloadSingleMissingToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}'
Assert-True ($reloadSingleMissingToken.StatusCode -eq 401) "reload missing token status code not returned"
Assert-True ($reloadSingleMissingToken.Body.code -eq -303) "reload missing token code not returned"
Assert-True ($reloadSingleMissingToken.Body.message -eq "admin token invalid") "reload missing token message not returned"

$reloadSingleInvalidToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = "wrong-token" }
Assert-True ($reloadSingleInvalidToken.StatusCode -eq 401) "reload invalid token status code not returned"
Assert-True ($reloadSingleInvalidToken.Body.code -eq -303) "reload invalid token code not returned"
Assert-True ($reloadSingleInvalidToken.Body.message -eq "admin token invalid") "reload invalid token message not returned"

if ($AdminToken -ne $DefaultAdminToken) {
    $reloadSingleDefaultToken = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $DefaultAdminToken }
    Assert-True ($reloadSingleDefaultToken.StatusCode -eq 401) "reload default token should be invalid when custom admin token is configured"
    Assert-True ($reloadSingleDefaultToken.Body.code -eq -303) "reload default token invalid code not returned"
}

$reloadSingle = Invoke-JsonRequest -Method "POST" -Url "$BaseUrl/api/v1/runtime/reload/face_detect" -Body '{}' -Headers @{ "X-Admin-Token" = $AdminToken }
Assert-True ($reloadSingle.code -eq 0) "single capability reload request failed"
Assert-True ($reloadSingle.data.capability_id -eq "face_detect") "single capability reload capability_id not returned"
Assert-True ($reloadSingle.data.reloaded -eq $true) "single capability reload result not returned"

$reloadMethodNotAllowed = Invoke-ErrorJsonRequest -Method "GET" -Url "$BaseUrl/api/v1/runtime/reload-all"
Assert-True ($reloadMethodNotAllowed.StatusCode -eq 405) "reload all 405 status code not returned"
Assert-True ($reloadMethodNotAllowed.Body.code -eq -405) "reload all 405 body code not returned"
Assert-True ($reloadMethodNotAllowed.Body.allow -eq "POST") "reload all allow method not returned"

$licenseReloadMethodNotAllowed = Invoke-ErrorJsonRequest -Method "GET" -Url "$BaseUrl/api/v1/license/reload"
Assert-True ($licenseReloadMethodNotAllowed.StatusCode -eq 405) "license reload 405 status code not returned"
Assert-True ($licenseReloadMethodNotAllowed.Body.code -eq -405) "license reload 405 body code not returned"
Assert-True ($licenseReloadMethodNotAllowed.Body.allow -eq "POST") "license reload allow method not returned"

$runtimeStatus = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/runtime/status"
Assert-True ($runtimeStatus.code -eq 0) "runtime status request failed"
Assert-True ($runtimeStatus.data.metrics.request_count -ge 2) "runtime status total request_count not updated"
Assert-True ($runtimeStatus.data.metrics.success_count -ge 1) "runtime status success_count not updated"
Assert-True ($runtimeStatus.data.metrics.failure_count -ge 1) "runtime status failure_count not updated"

$capabilitiesMethodNotAllowed = Invoke-ErrorJsonRequest -Method "POST" -Url "$BaseUrl/api/v1/capabilities" -Body '{}'
Assert-True ($capabilitiesMethodNotAllowed.StatusCode -eq 405) "capabilities 405 status code not returned"
Assert-True ($capabilitiesMethodNotAllowed.Body.code -eq -405) "capabilities 405 body code not returned"
Assert-True ($capabilitiesMethodNotAllowed.Body.allow -eq "GET") "capabilities allow method not returned"

$capabilitiesAfter = Invoke-JsonRequest -Method "GET" -Url "$BaseUrl/api/v1/capabilities"
Assert-True ($capabilitiesAfter.code -eq 0) "capabilities request after infer failed"
$faceCapabilityAfter = Get-CapabilityMetric -CapabilitiesResponse $capabilitiesAfter -CapabilityId "face_detect"
Assert-True ($null -ne $faceCapabilityAfter) "face_detect capability missing after infer"
Assert-True ($capabilitiesAfter.data.summary.metrics.request_count -ge 2) "capabilities summary request_count not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.success_count -ge 1) "capabilities summary success_count not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.failure_count -ge 1) "capabilities summary failure_count not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.last_success_timestamp -gt 0) "capabilities summary last_success_timestamp not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.last_failure_timestamp -gt 0) "capabilities summary last_failure_timestamp not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.last_failure_capability_id -eq "not_exist_cap") "capabilities summary last_failure_capability_id not updated"
Assert-True ($capabilitiesAfter.data.summary.metrics.last_failure_error_code -eq -200) "capabilities summary last_failure_error_code not updated"
Assert-True ($faceCapabilityAfter.metrics.success_count -ge 1) "capabilities face_detect success_count not updated"
Assert-True ($faceCapabilityAfter.metrics.last_success_timestamp -gt 0) "capabilities face_detect last_success_timestamp not updated"

Write-Host "api smoke test passed"
