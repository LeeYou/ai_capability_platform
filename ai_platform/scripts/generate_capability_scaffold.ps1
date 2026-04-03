param(
    [Parameter(Mandatory = $true)]
    [string]$CapabilityId,

    [Parameter(Mandatory = $true)]
    [string]$CapabilityName,

    [Parameter(Mandatory = $true)]
    [ValidateSet('image', 'video')]
    [string]$MediaMode,

    [switch]$WithActionParam
)

$ErrorActionPreference = 'Stop'

function New-ClassName {
    param([string]$Value)
    $parts = $Value.Split('_', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts.Count -eq 0) {
        throw 'CapabilityId must not be empty.'
    }
    return ($parts | ForEach-Object { $_.Substring(0, 1).ToUpper() + $_.Substring(1) }) -join ''
}

function Write-NewFile {
    param(
        [string]$Path,
        [string]$Content
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }
    if (Test-Path $Path) {
        throw "Refusing to overwrite existing file: $Path"
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
}

function Add-UniqueBlock {
    param(
        [string]$Path,
        [string]$Anchor,
        [string]$Block,
        [string]$MatchText
    )

    if (-not (Test-Path $Path)) {
        throw "Target file not found: $Path"
    }

    $content = Get-Content -Path $Path -Raw
    if ($content.Contains($MatchText)) {
        return $false
    }
    if (-not $content.Contains($Anchor)) {
        throw "Anchor not found in ${Path}: ${Anchor}"
    }

    $updated = $content.Replace($Anchor, "$Anchor`r`n$Block")
    Set-Content -Path $Path -Value $updated -Encoding UTF8
    return $true
}

function Add-UniqueTailBlock {
    param(
        [string]$Path,
        [string]$Block,
        [string]$MatchText
    )

    if (-not (Test-Path $Path)) {
        throw "Target file not found: $Path"
    }

    $content = Get-Content -Path $Path -Raw
    if ($content.Contains($MatchText)) {
        return $false
    }

    $normalized = $content.TrimEnd("`r", "`n")
    $updated = $normalized + "`r`n`r`n" + $Block.Trim() + "`r`n"
    Set-Content -Path $Path -Value $updated -Encoding UTF8
    return $true
}

function Add-JniBlocks {
    param(
        [string]$Path,
        [string]$CapabilityId,
        [string]$BridgeName,
        [string]$DemoName
    )

    if (-not (Test-Path $Path)) {
        throw "Target file not found: $Path"
    }

    $content = Get-Content -Path $Path -Raw
    if ($content.Contains("add_library(ai_jni_${CapabilityId} SHARED")) {
        return $false
    }

    $jniBlock = @"

    add_library(ai_jni_${CapabilityId} SHARED
        ${CapabilityId}_jni.cpp
    )

    target_include_directories(ai_jni_${CapabilityId} PRIVATE
        `${CMAKE_SOURCE_DIR}/include
        `${CMAKE_CURRENT_SOURCE_DIR}
        `${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        `${JNI_INCLUDE_DIRS}
    )

    target_link_libraries(ai_jni_${CapabilityId} PRIVATE
        ai_jni_bridge_common
        ai_sdk_${CapabilityId}
    )
"@

    $updated = [regex]::Replace(
        $content,
        '(?s)(if\(JNI_FOUND\).*?)(\r?\nendif\(\))',
        ('$1' + $jniBlock + '$2'),
        1
    )

    if ($updated -eq $content) {
        throw 'Failed to insert JNI capability block.'
    }

    $javaLines = "`r`n        `${CMAKE_CURRENT_SOURCE_DIR}/${BridgeName}.java`r`n        `${CMAKE_CURRENT_SOURCE_DIR}/${DemoName}.java"
    $updated2 = [regex]::Replace(
        $updated,
        '(?s)(set\(AI_JNI_JAVA_SOURCES.*?)(\r?\n\s*\))',
        ('$1' + $javaLines + '$2'),
        1
    )

    if ($updated2 -eq $updated) {
        throw 'Failed to insert Java JNI source entries.'
    }

    Set-Content -Path $Path -Value $updated2 -Encoding UTF8
    return $true
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$capabilitySnake = $CapabilityId.Trim().ToLower()
if ($capabilitySnake -notmatch '^[a-z0-9_]+$') {
    throw 'CapabilityId must use lower_snake_case.'
}

$capabilityClass = New-ClassName -Value $capabilitySnake
$sdkClassName = "${capabilityClass}Sdk"
$dllStructName = "Ai${capabilityClass}DllResult"
$jniBridgeName = "${capabilityClass}JniBridge"
$jniDemoName = "${capabilityClass}JniDemo"
$upperSnake = $capabilitySnake.ToUpper()

$pluginDir = Join-Path $repoRoot "src/plugins/$capabilitySnake"
$linuxSdkDir = Join-Path $repoRoot 'src/sdk/linux_so'
$windowsDllDir = Join-Path $repoRoot 'src/sdk/windows_dll'
$jniDir = Join-Path $repoRoot 'src/jni'
$pluginsCMakePath = Join-Path $repoRoot 'src/plugins/CMakeLists.txt'
$linuxCMakePath = Join-Path $linuxSdkDir 'CMakeLists.txt'
$windowsCMakePath = Join-Path $windowsDllDir 'CMakeLists.txt'
$jniCMakePath = Join-Path $jniDir 'CMakeLists.txt'

$sdkMethodDeclaration = if ($MediaMode -eq 'video') {
    if ($WithActionParam) {
        "${capabilityClass}SdkResult infer_video_base64(const std::string& media_base64, const std::string& media_format, const std::string& action) const;"
    } else {
        "${capabilityClass}SdkResult infer_video_base64(const std::string& media_base64, const std::string& media_format) const;"
    }
} else {
    "${capabilityClass}SdkResult infer_image_base64(const std::string& image_base64, const std::string& image_format) const;"
}

$pluginInfoJson = if ($MediaMode -eq 'video') { '{"supports_video":true}' } else { '{"supports_single_image":true}' }

$pluginContent = @"
#include "ai_platform/ai_plugin_api.h"

#include <cstring>
#include <new>
#include <string>

namespace {
struct ${capabilityClass}Context {
    const char* version = "0.1.0";
};
}

extern "C" {

AI_PLUGIN_EXPORT int ai_plugin_init(const AiPluginInitParams* params, AiPluginHandle* out_handle) {
    if (!params || !out_handle) {
        return -2;
    }
    auto* ctx = new (std::nothrow) ${capabilityClass}Context();
    if (!ctx) {
        return -4;
    }
    *out_handle = ctx;
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_destroy(AiPluginHandle handle) {
    if (!handle) {
        return -3;
    }
    delete static_cast<${capabilityClass}Context*>(handle);
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_infer(AiPluginHandle handle, const AiPluginInput* input, AiPluginOutput* output) {
    if (!handle || !input || !output) {
        return -2;
    }

    std::string json = "{\"mock\":true,\"capability_id\":\"$capabilitySnake\"}";
    const auto len = json.size();
    output->result_json = new char[len + 1];
    std::memcpy(output->result_json, json.c_str(), len + 1);
    output->result_code = 0;
    output->error_message = nullptr;
    output->infer_time_ms = 0.1;
    return 0;
}

AI_PLUGIN_EXPORT void ai_plugin_free_result(AiPluginOutput* output) {
    if (output && output->result_json) {
        delete[] output->result_json;
        output->result_json = nullptr;
    }
}

AI_PLUGIN_EXPORT int ai_plugin_reload(AiPluginHandle handle, const char* new_model_dir) {
    (void)handle;
    (void)new_model_dir;
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_get_info(AiPluginHandle handle, AiPluginInfo* info) {
    if (!handle || !info) {
        return -2;
    }
    info->capability_id = "$capabilitySnake";
    info->capability_name = "$CapabilityName";
    info->version = "0.1.0";
    info->model_version = "mock";
    info->description = "Mock $capabilitySnake plugin";
    info->api_version_major = 1;
    info->api_version_minor = 0;
    info->api_version_patch = 0;
    info->current_device = AI_DEVICE_CPU;
    info->extra_info_json = "$pluginInfoJson";
    return 0;
}

}
"@

$linuxHeaderContent = @"
#ifndef AI_PLATFORM_${upperSnake}_SDK_H
#define AI_PLATFORM_${upperSnake}_SDK_H

#include "capability_sdk.h"

#include <string>

namespace ai_platform {

using ${capabilityClass}SdkResult = CapabilitySdkResult;

class ${sdkClassName} {
public:
    ${sdkClassName}();
    ~${sdkClassName}();

    bool initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path = std::string());
    $sdkMethodDeclaration
    std::string last_error() const;
    std::string last_license_failure_reason() const;
    std::string last_license_failure_detail() const;
    std::string capability_id() const;

private:
    class Impl;
    Impl* impl_ = nullptr;
};

}

#endif
"@

$linuxCppContent = @"
#include "${capabilitySnake}_sdk.h"

namespace ai_platform {

class ${sdkClassName}::Impl {
public:
    CapabilitySdk sdk;
};

${sdkClassName}::${sdkClassName}() = default;

${sdkClassName}::~${sdkClassName}() {
    delete impl_;
    impl_ = nullptr;
}

bool ${sdkClassName}::initialize(const std::string& library_path, const std::string& model_dir, const std::string& license_path) {
    if (!impl_) {
        impl_ = new Impl();
    }
    return impl_->sdk.initialize(library_path, model_dir, license_path);
}

${capabilityClass}SdkResult ${sdkClassName}::$sdkMethodDeclaration {
    if (!impl_) {
        ${capabilityClass}SdkResult result;
        result.error_message = "sdk not initialized";
        return result;
    }
    // TODO: implement inference method
}

std::string ${sdkClassName}::last_error() const {
    if (!impl_) {
        return "sdk not initialized";
    }
    return impl_->sdk.last_error();
}

std::string ${sdkClassName}::last_license_failure_reason() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.last_license_failure_reason();
}

std::string ${sdkClassName}::last_license_failure_detail() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.last_license_failure_detail();
}

std::string ${sdkClassName}::capability_id() const {
    if (!impl_) {
        return std::string();
    }
    return impl_->sdk.capability_id();
}

}
"@

$linuxSampleContent = @"
#include "${capabilitySnake}_sdk.h"

int main() {
    return 0;
}
"@

$linuxTestContent = @"
#include "${capabilitySnake}_sdk.h"

int main() {
    return 0;
}
"@

$dllHeaderContent = @"
#ifndef AI_PLATFORM_${upperSnake}_DLL_H
#define AI_PLATFORM_${upperSnake}_DLL_H

#include "dll_exports.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int code;
    const char* result_json;
    const char* error_message;
} ${dllStructName};

AI_SDK_EXPORT int ai_${capabilitySnake}_sdk_version();
AI_SDK_EXPORT int ai_${capabilitySnake}_initialize(const char* plugin_path, const char* model_dir, const char* license_path);
AI_SDK_EXPORT const char* ai_${capabilitySnake}_capability_id();
AI_SDK_EXPORT const char* ai_${capabilitySnake}_last_license_failure_reason();
AI_SDK_EXPORT const char* ai_${capabilitySnake}_last_license_failure_detail();
AI_SDK_EXPORT ${dllStructName} ai_${capabilitySnake}_infer_base64(const char* media_base64, const char* media_format);
AI_SDK_EXPORT void ai_${capabilitySnake}_shutdown();

#ifdef __cplusplus
}
#endif

#endif
"@

$dllCppContent = @"
#include "${capabilitySnake}_dll.h"

#include "${capabilitySnake}_sdk.h"

extern "C" AI_SDK_EXPORT int ai_${capabilitySnake}_sdk_version() {
    return 1;
}

extern "C" AI_SDK_EXPORT int ai_${capabilitySnake}_initialize(const char* plugin_path, const char* model_dir, const char* license_path) {
    // TODO: implement initialization
    return 0;
}

extern "C" AI_SDK_EXPORT const char* ai_${capabilitySnake}_capability_id() {
    return "$capabilitySnake";
}

extern "C" AI_SDK_EXPORT const char* ai_${capabilitySnake}_last_license_failure_reason() {
    return "";
}

extern "C" AI_SDK_EXPORT const char* ai_${capabilitySnake}_last_license_failure_detail() {
    return "";
}

extern "C" AI_SDK_EXPORT ${dllStructName} ai_${capabilitySnake}_infer_base64(const char* media_base64, const char* media_format) {
    // TODO: implement inference
    ${dllStructName} result;
    result.code = 0;
    result.result_json = "{\"mock\":true}";
    result.error_message = nullptr;
    return result;
}

extern "C" AI_SDK_EXPORT void ai_${capabilitySnake}_shutdown() {
    // TODO: implement shutdown
}
"@

$dllSampleContent = @"
#include "${capabilitySnake}_dll.h"

int main() {
    return 0;
}
"@

$dllTestContent = @"
#include "${capabilitySnake}_dll.h"

int main() {
    return 0;
}
"@

$jniCppContent = @"
#include <jni.h>

#include "jni_bridge_common.h"
#include "${capabilitySnake}_sdk.h"

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_${jniBridgeName}_nativeVersion(JNIEnv* env, jclass) {
    return env->NewStringUTF(ai_platform::jni_bridge_version().c_str());
}
"@

$jniBridgeContent = @"
package ai.platform.sdk;

public final class ${jniBridgeName} {
    private ${jniBridgeName}() {
    }

    public static void loadLibrary(String libraryName) {
        System.loadLibrary(libraryName);
    }
}
"@

$jniDemoContent = @"
package ai.platform.sdk;

public final class ${jniDemoName} {
    private ${jniDemoName}() {
    }

    public static void main(String[] args) {
        ${jniBridgeName}.loadLibrary(args[0]);
    }
}
"@

$files = @(
    @{ Path = Join-Path $pluginDir "${capabilitySnake}_plugin.cpp"; Content = $pluginContent },
    @{ Path = Join-Path $linuxSdkDir "${capabilitySnake}_sdk.h"; Content = $linuxHeaderContent },
    @{ Path = Join-Path $linuxSdkDir "${capabilitySnake}_sdk.cpp"; Content = $linuxCppContent },
    @{ Path = Join-Path $linuxSdkDir "${capabilitySnake}_sdk_sample.cpp"; Content = $linuxSampleContent },
    @{ Path = Join-Path $linuxSdkDir "test_${capabilitySnake}_sdk.cpp"; Content = $linuxTestContent },
    @{ Path = Join-Path $windowsDllDir "${capabilitySnake}_dll.h"; Content = $dllHeaderContent },
    @{ Path = Join-Path $windowsDllDir "${capabilitySnake}_dll.cpp"; Content = $dllCppContent },
    @{ Path = Join-Path $windowsDllDir "${capabilitySnake}_dll_sample.cpp"; Content = $dllSampleContent },
    @{ Path = Join-Path $windowsDllDir "test_${capabilitySnake}_dll.cpp"; Content = $dllTestContent },
    @{ Path = Join-Path $jniDir "${capabilitySnake}_jni.cpp"; Content = $jniCppContent },
    @{ Path = Join-Path $jniDir "${jniBridgeName}.java"; Content = $jniBridgeContent },
    @{ Path = Join-Path $jniDir "${jniDemoName}.java"; Content = $jniDemoContent }
)

foreach ($file in $files) {
    Write-NewFile -Path $file.Path -Content $file.Content
}

$null = Add-UniqueTailBlock -Path $pluginsCMakePath -Block "add_capability_plugin($capabilitySnake)" -MatchText "add_capability_plugin($capabilitySnake)"

$linuxCMakeBlock = @"
add_library(ai_sdk_${capabilitySnake} STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    ${capabilitySnake}_sdk.cpp
)

target_include_directories(ai_sdk_${capabilitySnake} PUBLIC
    `${CMAKE_SOURCE_DIR}/include
    `${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_${capabilitySnake} PRIVATE
    ai_license
)

add_executable(ai_sdk_${capabilitySnake}_sample
    ${capabilitySnake}_sdk_sample.cpp
)

add_executable(test_${capabilitySnake}_sdk
    test_${capabilitySnake}_sdk.cpp
)

target_include_directories(ai_sdk_${capabilitySnake}_sample PRIVATE
    `${CMAKE_SOURCE_DIR}/include
    `${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_${capabilitySnake}_sdk PRIVATE
    `${CMAKE_SOURCE_DIR}/include
    `${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_${capabilitySnake}_sample PRIVATE
    ai_sdk_${capabilitySnake}
)

target_link_libraries(test_${capabilitySnake}_sdk PRIVATE
    ai_sdk_${capabilitySnake}
    ai_license
)

add_test(
    NAME test_${capabilitySnake}_sdk
    COMMAND test_${capabilitySnake}_sdk
        `${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/`$<CONFIG>/libcap_${capabilitySnake}.dll
        `${CMAKE_SOURCE_DIR}
)
"@
$null = Add-UniqueTailBlock -Path $linuxCMakePath -Block $linuxCMakeBlock -MatchText "add_library(ai_sdk_${capabilitySnake} STATIC"

$windowsCMakeBlock = @"
add_library(ai_${capabilitySnake}_sdk SHARED
    ${capabilitySnake}_dll.cpp
)

target_include_directories(ai_${capabilitySnake}_sdk PUBLIC
    `${CMAKE_CURRENT_SOURCE_DIR}
    `${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_link_libraries(ai_${capabilitySnake}_sdk PRIVATE
    ai_sdk_${capabilitySnake}
)

add_executable(${capabilitySnake}_dll_sample
    ${capabilitySnake}_dll_sample.cpp
)

add_executable(test_${capabilitySnake}_dll
    test_${capabilitySnake}_dll.cpp
)

target_include_directories(${capabilitySnake}_dll_sample PRIVATE
    `${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_${capabilitySnake}_dll PRIVATE
    `${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(${capabilitySnake}_dll_sample PRIVATE
    ai_${capabilitySnake}_sdk
)

target_link_libraries(test_${capabilitySnake}_dll PRIVATE
    ai_${capabilitySnake}_sdk
    ai_license
)

add_test(
    NAME test_${capabilitySnake}_dll
    COMMAND test_${capabilitySnake}_dll
        `${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/`$<CONFIG>/libcap_${capabilitySnake}.dll
        `${CMAKE_SOURCE_DIR}
)
"@
$null = Add-UniqueTailBlock -Path $windowsCMakePath -Block $windowsCMakeBlock -MatchText "add_library(ai_${capabilitySnake}_sdk SHARED"

$null = Add-JniBlocks -Path $jniCMakePath -CapabilityId $capabilitySnake -BridgeName $jniBridgeName -DemoName $jniDemoName

Write-Host "Generated scaffold for capability: $capabilitySnake"
Write-Host ""
Write-Host "Generated files:"
foreach ($file in $files) {
    Write-Host "- $($file.Path.Replace($repoRoot + [System.IO.Path]::DirectorySeparatorChar, ''))"
}
Write-Host ""
Write-Host "Manual follow-up still required:"
Write-Host "- Fill in ${capabilitySnake}_sdk.cpp inference method body"
Write-Host "- Fill in ai_${capabilitySnake}_infer_base64 export implementation"
Write-Host "- Expand JNI bridge methods beyond nativeVersion"
Write-Host "- Review auto-appended CMake target wiring in src/plugins/CMakeLists.txt, src/sdk/linux_so/CMakeLists.txt, src/sdk/windows_dll/CMakeLists.txt, src/jni/CMakeLists.txt"
Write-Host "- Add registry entry and acceptance docs"
Write-Host "- Build and run ctest"
