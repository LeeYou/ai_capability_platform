#ifndef AI_PLATFORM_AI_PLUGIN_API_H
#define AI_PLATFORM_AI_PLUGIN_API_H

#include <stddef.h>
#include <stdint.h>

#ifdef _WIN32
#define AI_PLUGIN_EXPORT __declspec(dllexport)
#else
#define AI_PLUGIN_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef void* AiPluginHandle;

typedef enum {
    AI_DEVICE_CPU = 0,
    AI_DEVICE_CUDA = 1
} AiDeviceType;

typedef enum {
    AI_MEDIA_TYPE_IMAGE = 0,
    AI_MEDIA_TYPE_VIDEO = 1,
    AI_MEDIA_TYPE_FRAME_SEQUENCE = 2
} AiMediaType;

typedef struct {
    const char* model_dir;
    AiDeviceType device;
    int device_id;
    int max_batch_size;
    const char* extra_config;
    int log_level;
} AiPluginInitParams;

typedef struct {
    const uint8_t* data;
    int width;
    int height;
    int channels;
    int stride;
    size_t data_size;
    int format;
} AiImage;

typedef struct {
    const AiImage* images;
    int image_count;
    const uint8_t* media_data;
    size_t media_size;
    AiMediaType media_type;
    const char* media_format;
    const char* params_json;
} AiPluginInput;

typedef struct {
    char* result_json;
    int result_code;
    const char* error_message;
    double infer_time_ms;
} AiPluginOutput;

typedef struct {
    const char* capability_id;
    const char* capability_name;
    const char* version;
    const char* model_version;
    const char* description;
    int api_version_major;
    int api_version_minor;
    int api_version_patch;
    AiDeviceType current_device;
    const char* extra_info_json;
} AiPluginInfo;

typedef int (*fn_ai_plugin_init)(const AiPluginInitParams*, AiPluginHandle*);
typedef int (*fn_ai_plugin_destroy)(AiPluginHandle);
typedef int (*fn_ai_plugin_infer)(AiPluginHandle, const AiPluginInput*, AiPluginOutput*);
typedef void (*fn_ai_plugin_free_result)(AiPluginOutput*);
typedef int (*fn_ai_plugin_reload)(AiPluginHandle, const char*);
typedef int (*fn_ai_plugin_get_info)(AiPluginHandle, AiPluginInfo*);
typedef int (*fn_ai_plugin_warmup)(AiPluginHandle);
typedef int (*fn_ai_plugin_health_check)(AiPluginHandle);

#ifdef __cplusplus
}
#endif

#endif
