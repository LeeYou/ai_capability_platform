#include "ai_platform/ai_plugin_api.h"

#include <nlohmann/json.hpp>

#include <cstring>
#include <new>
#include <string>

namespace {
struct LivenessActionContext {
    const char* version = "0.1.0";
};

const char* to_media_type_name(AiMediaType media_type) {
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
    if (!params || !out_handle) {
        return -2;
    }
    auto* ctx = new (std::nothrow) LivenessActionContext();
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
    delete static_cast<LivenessActionContext*>(handle);
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_infer(AiPluginHandle handle, const AiPluginInput* input, AiPluginOutput* output) {
    if (!handle || !input || !output) {
        return -2;
    }

    std::string action = "blink";
    if (input->params_json != nullptr && input->params_json[0] != '\0') {
        try {
            const auto params = nlohmann::json::parse(input->params_json);
            if (params.is_object() && params.contains("action") && params["action"].is_string() && !params["action"].get<std::string>().empty()) {
                action = params["action"].get<std::string>();
            }
        } catch (const nlohmann::json::parse_error&) {
        }
    }
    const bool has_video_media = input->media_type == AI_MEDIA_TYPE_VIDEO && input->media_size > 0;
    const bool has_frame_sequence = input->media_type == AI_MEDIA_TYPE_FRAME_SEQUENCE && input->image_count > 1;
    const bool passed = has_video_media || has_frame_sequence;

    std::string json = "{\"is_live\":";
    json += passed ? "true" : "false";
    json += ",\"score\":";
    json += passed ? "0.98" : "0.12";
    json += ",\"action_results\":[{\"action\":\"" + action + "\",\"passed\":";
    json += passed ? "true" : "false";
    json += "}],\"mock\":true,\"input_summary\":{";
    json += "\"media_type\":\"";
    json += to_media_type_name(input->media_type);
    json += "\",";
    json += "\"image_count\":" + std::to_string(input->image_count) + ",";
    json += "\"media_size\":" + std::to_string(static_cast<unsigned long long>(input->media_size)) + ",";
    json += "\"media_format\":\"";
    json += input->media_format ? input->media_format : "";
    json += "\",";
    json += "\"action\":\"" + action + "\"}}";

    const auto len = json.size();
    output->result_json = new char[len + 1];
    std::memcpy(output->result_json, json.c_str(), len + 1);
    output->result_code = 0;
    output->error_message = nullptr;
    output->infer_time_ms = 1.2;
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
    info->capability_id = "liveness_action";
    info->capability_name = "指令活体检测";
    info->version = "0.1.0";
    info->model_version = "mock";
    info->description = "Mock liveness action plugin for video request MVP";
    info->api_version_major = 1;
    info->api_version_minor = 0;
    info->api_version_patch = 0;
    info->current_device = AI_DEVICE_CPU;
    info->extra_info_json = "{\"supports_video\":true}";
    return 0;
}

}
