#ifndef AI_PLATFORM_DOC_CLASSIFY_DLL_H
#define AI_PLATFORM_DOC_CLASSIFY_DLL_H

#include "dll_exports.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int code;
    const char* result_json;
    const char* error_message;
} AiDocClassifyDllResult;

AI_SDK_EXPORT int ai_doc_classify_sdk_version();
AI_SDK_EXPORT int ai_doc_classify_initialize(const char* plugin_path, const char* model_dir, const char* license_path);
AI_SDK_EXPORT const char* ai_doc_classify_capability_id();
AI_SDK_EXPORT const char* ai_doc_classify_last_license_failure_reason();
AI_SDK_EXPORT const char* ai_doc_classify_last_license_failure_detail();
AI_SDK_EXPORT AiDocClassifyDllResult ai_doc_classify_infer_base64(const char* image_base64, const char* image_format);
AI_SDK_EXPORT void ai_doc_classify_shutdown();

#ifdef __cplusplus
}
#endif

#endif
