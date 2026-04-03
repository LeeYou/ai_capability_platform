#include "ai_platform/ai_plugin_api.h"

#include <cstring>
#include <new>
#include <string>

namespace {

struct MockPluginContext {
    std::string model_dir;
    AiDeviceType device = AI_DEVICE_CPU;
    int max_batch_size = 1;
    std::string extra_info_json = "{}";
    int warmup_count = 0;
    int health_check_count = 0;
};

const char* ToMediaTypeName(AiMediaType media_type) {
    switch (media_type) {
        case AI_MEDIA_TYPE_VIDEO:
            return "video";
        case AI_MEDIA_TYPE_FRAME_SEQUENCE:
            return "frame_sequence";
        case AI_MEDIA_TYPE_IMAGE:
        default:
            return "image";
    }
}

}

extern "C" {

AI_PLUGIN_EXPORT int ai_plugin_init(const AiPluginInitParams* params, AiPluginHandle* out_handle) {
    if (params == nullptr || out_handle == nullptr) {
        return -2;
    }
    auto* context = new (std::nothrow) MockPluginContext();
    if (context == nullptr) {
        return -4;
    }
    context->model_dir = params->model_dir != nullptr ? params->model_dir : "";
    context->device = params->device;
    context->max_batch_size = params->max_batch_size > 0 ? params->max_batch_size : 1;
    context->extra_info_json = "{\"max_batch_size\":" + std::to_string(context->max_batch_size) + "}";
    *out_handle = context;
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_destroy(AiPluginHandle handle) {
    if (handle == nullptr) {
        return -3;
    }
    delete static_cast<MockPluginContext*>(handle);
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_infer(AiPluginHandle handle, const AiPluginInput* input, AiPluginOutput* output) {
    if (handle == nullptr || input == nullptr || output == nullptr) {
        return -2;
    }
    const auto* context = static_cast<const MockPluginContext*>(handle);
    std::string json = "{\"mock\":true,";
    json += "\"model_dir\":\"" + context->model_dir + "\",";
    json += "\"device\":\"";
    json += context->device == AI_DEVICE_CUDA ? "cuda" : "cpu";
    json += "\",";
    json += "\"max_batch_size\":" + std::to_string(context->max_batch_size) + ",";
    json += "\"media_type\":\"";
    json += ToMediaTypeName(input->media_type);
    json += "\",";
    json += "\"media_format\":\"";
    json += input->media_format != nullptr ? input->media_format : "";
    json += "\",";
    json += "\"media_size\":" + std::to_string(static_cast<unsigned long long>(input->media_size));
    json += "}";
    output->result_json = new char[json.size() + 1];
    std::memcpy(output->result_json, json.c_str(), json.size() + 1);
    output->result_code = 0;
    output->error_message = nullptr;
    output->infer_time_ms = 1.5;
    return 0;
}

AI_PLUGIN_EXPORT void ai_plugin_free_result(AiPluginOutput* output) {
    if (output != nullptr && output->result_json != nullptr) {
        delete[] output->result_json;
        output->result_json = nullptr;
    }
}

AI_PLUGIN_EXPORT int ai_plugin_reload(AiPluginHandle, const char*) {
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_get_info(AiPluginHandle handle, AiPluginInfo* info) {
    if (handle == nullptr || info == nullptr) {
        return -2;
    }
    info->capability_id = "mock_capability";
    info->capability_name = "Mock Capability";
    info->version = "1.0.0";
    info->model_version = "mock";
    info->description = "Mock test plugin";
    info->api_version_major = 1;
    info->api_version_minor = 0;
    info->api_version_patch = 0;
    info->current_device = static_cast<MockPluginContext*>(handle)->device;
    info->extra_info_json = static_cast<MockPluginContext*>(handle)->extra_info_json.c_str();
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_warmup(AiPluginHandle handle) {
    if (handle == nullptr) {
        return -2;
    }
    auto* context = static_cast<MockPluginContext*>(handle);
    context->warmup_count += 1;
    return context->model_dir.find("warmup_fail") == std::string::npos ? 0 : -5;
}

AI_PLUGIN_EXPORT int ai_plugin_health_check(AiPluginHandle handle) {
    if (handle == nullptr) {
        return -2;
    }
    auto* context = static_cast<MockPluginContext*>(handle);
    context->health_check_count += 1;
    return context->model_dir.find("health_fail") == std::string::npos ? 0 : -6;
}

}
