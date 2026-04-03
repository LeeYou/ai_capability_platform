#ifndef AI_PLATFORM_SDK_LOADER_H
#define AI_PLATFORM_SDK_LOADER_H

#include "ai_platform/ai_plugin_api.h"

#include <string>

namespace ai_platform {

class SdkLoader {
public:
    SdkLoader();
    ~SdkLoader();

    bool initialize(const std::string& library_path, const std::string& model_dir);
    void unload();
    bool is_ready() const;
    bool infer(const AiPluginInput& input, std::string* result_json, int* result_code, std::string* error_message) const;
    std::string last_error() const;
    std::string capability_id() const;

private:
    void* module_ = nullptr;
    AiPluginHandle handle_ = nullptr;
    fn_ai_plugin_init init_ = nullptr;
    fn_ai_plugin_destroy destroy_ = nullptr;
    fn_ai_plugin_infer infer_ = nullptr;
    fn_ai_plugin_free_result free_result_ = nullptr;
    fn_ai_plugin_get_info get_info_ = nullptr;
    AiPluginInfo plugin_info_{};
    std::string library_path_;
    std::string model_dir_;
    std::string last_error_;
};

}

#endif
