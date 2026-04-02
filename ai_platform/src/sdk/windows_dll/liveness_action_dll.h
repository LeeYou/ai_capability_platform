#ifndef AI_PLATFORM_LIVENESS_ACTION_DLL_H
#define AI_PLATFORM_LIVENESS_ACTION_DLL_H

#include "dll_exports.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int code;
    const char* result_json;
    const char* error_message;
} AiLivenessActionDllResult;

AI_SDK_EXPORT int ai_liveness_action_sdk_version();
AI_SDK_EXPORT int ai_liveness_action_initialize(const char* plugin_path, const char* model_dir, const char* license_path);
AI_SDK_EXPORT const char* ai_liveness_action_capability_id();
AI_SDK_EXPORT const char* ai_liveness_action_last_license_failure_reason();
AI_SDK_EXPORT const char* ai_liveness_action_last_license_failure_detail();
AI_SDK_EXPORT AiLivenessActionDllResult ai_liveness_action_infer_base64(const char* media_base64, const char* media_format, const char* action);
AI_SDK_EXPORT void ai_liveness_action_shutdown();

#ifdef __cplusplus
}
#endif

#endif
