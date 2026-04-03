#include "liveness_action_dll.h"

#include "liveness_action_sdk.h"

#include <memory>
#include <string>

namespace {

std::unique_ptr<ai_platform::LivenessActionSdk> g_sdk;
std::string g_result_json;
std::string g_error_message;
std::string g_capability_id;
std::string g_license_failure_reason;
std::string g_license_failure_detail;

AiLivenessActionDllResult make_result(int code, const std::string& result_json, const std::string& error_message) {
    g_result_json = result_json;
    g_error_message = error_message;
    AiLivenessActionDllResult result{};
    result.code = code;
    result.result_json = g_result_json.c_str();
    result.error_message = g_error_message.empty() ? nullptr : g_error_message.c_str();
    return result;
}

}

extern "C" AI_SDK_EXPORT int ai_liveness_action_sdk_version() {
    return 1;
}

extern "C" AI_SDK_EXPORT int ai_liveness_action_initialize(const char* plugin_path, const char* model_dir, const char* license_path) {
    g_sdk = std::make_unique<ai_platform::LivenessActionSdk>();
    if (!g_sdk->initialize(plugin_path ? plugin_path : "", model_dir ? model_dir : "", license_path ? license_path : "")) {
        g_error_message = g_sdk->last_error();
        g_license_failure_reason = g_sdk->last_license_failure_reason();
        g_license_failure_detail = g_sdk->last_license_failure_detail();
        g_sdk.reset();
        return -1;
    }
    g_capability_id = g_sdk->capability_id();
    g_error_message.clear();
    g_license_failure_reason.clear();
    g_license_failure_detail.clear();
    return 0;
}

extern "C" AI_SDK_EXPORT const char* ai_liveness_action_capability_id() {
    return g_capability_id.c_str();
}

extern "C" AI_SDK_EXPORT const char* ai_liveness_action_last_license_failure_reason() {
    return g_license_failure_reason.empty() ? nullptr : g_license_failure_reason.c_str();
}

extern "C" AI_SDK_EXPORT const char* ai_liveness_action_last_license_failure_detail() {
    return g_license_failure_detail.empty() ? nullptr : g_license_failure_detail.c_str();
}

extern "C" AI_SDK_EXPORT AiLivenessActionDllResult ai_liveness_action_infer_base64(const char* media_base64, const char* media_format, const char* action) {
    if (!g_sdk) {
        return make_result(-1, "", "sdk not initialized");
    }

    const auto infer_result = g_sdk->infer_video_base64(media_base64 ? media_base64 : "", media_format ? media_format : "mp4", action ? action : "blink");
    return make_result(infer_result.code, infer_result.result_json, infer_result.ok ? std::string() : infer_result.error_message);
}

extern "C" AI_SDK_EXPORT void ai_liveness_action_shutdown() {
    g_sdk.reset();
    g_result_json.clear();
    g_error_message.clear();
    g_capability_id.clear();
    g_license_failure_reason.clear();
    g_license_failure_detail.clear();
}
