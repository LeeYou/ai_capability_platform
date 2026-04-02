#include "sdk_loader.h"

#include "ai_platform/ai_plugin_api.h"

#include <cstring>
#include <string>
#include <utility>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace ai_platform {

SdkLoader::SdkLoader() = default;

SdkLoader::~SdkLoader() {
    unload();
}

bool SdkLoader::initialize(const std::string& library_path, const std::string& model_dir) {
    unload();

#ifdef _WIN32
    module_ = LoadLibraryA(library_path.c_str());
    if (!module_) {
        last_error_ = "load plugin library failed";
        return false;
    }
    init_ = reinterpret_cast<fn_ai_plugin_init>(GetProcAddress(static_cast<HMODULE>(module_), "ai_plugin_init"));
    destroy_ = reinterpret_cast<fn_ai_plugin_destroy>(GetProcAddress(static_cast<HMODULE>(module_), "ai_plugin_destroy"));
    infer_ = reinterpret_cast<fn_ai_plugin_infer>(GetProcAddress(static_cast<HMODULE>(module_), "ai_plugin_infer"));
    free_result_ = reinterpret_cast<fn_ai_plugin_free_result>(GetProcAddress(static_cast<HMODULE>(module_), "ai_plugin_free_result"));
    get_info_ = reinterpret_cast<fn_ai_plugin_get_info>(GetProcAddress(static_cast<HMODULE>(module_), "ai_plugin_get_info"));
#else
    module_ = dlopen(library_path.c_str(), RTLD_LAZY);
    if (!module_) {
        last_error_ = "load plugin library failed";
        return false;
    }
    init_ = reinterpret_cast<fn_ai_plugin_init>(dlsym(module_, "ai_plugin_init"));
    destroy_ = reinterpret_cast<fn_ai_plugin_destroy>(dlsym(module_, "ai_plugin_destroy"));
    infer_ = reinterpret_cast<fn_ai_plugin_infer>(dlsym(module_, "ai_plugin_infer"));
    free_result_ = reinterpret_cast<fn_ai_plugin_free_result>(dlsym(module_, "ai_plugin_free_result"));
    get_info_ = reinterpret_cast<fn_ai_plugin_get_info>(dlsym(module_, "ai_plugin_get_info"));
#endif

    if (!init_ || !destroy_ || !infer_ || !free_result_ || !get_info_) {
        last_error_ = "plugin symbols incomplete";
        unload();
        return false;
    }

    AiPluginInitParams init_params{};
    init_params.model_dir = model_dir.c_str();
    init_params.device = AI_DEVICE_CPU;
    init_params.device_id = 0;
    init_params.max_batch_size = 1;
    init_params.extra_config = "{}";
    init_params.log_level = 3;

    if (init_(&init_params, &handle_) != 0) {
        last_error_ = "plugin init failed";
        unload();
        return false;
    }

    std::memset(&plugin_info_, 0, sizeof(plugin_info_));
    get_info_(handle_, &plugin_info_);
    library_path_ = library_path;
    model_dir_ = model_dir;
    last_error_.clear();
    return true;
}

void SdkLoader::unload() {
    if (destroy_ && handle_) {
        destroy_(handle_);
    }
    handle_ = nullptr;
    init_ = nullptr;
    destroy_ = nullptr;
    infer_ = nullptr;
    free_result_ = nullptr;
    get_info_ = nullptr;
#ifdef _WIN32
    if (module_) {
        FreeLibrary(static_cast<HMODULE>(module_));
    }
#else
    if (module_) {
        dlclose(module_);
    }
#endif
    module_ = nullptr;
}

bool SdkLoader::is_ready() const {
    return handle_ != nullptr && infer_ != nullptr;
}

bool SdkLoader::infer(const AiPluginInput& input, std::string* result_json, int* result_code, std::string* error_message) const {
    if (!is_ready() || !result_json || !result_code || !error_message) {
        return false;
    }

    AiPluginOutput output{};
    const int rc = infer_(handle_, &input, &output);
    *result_code = output.result_code;
    *result_json = output.result_json ? output.result_json : "";
    *error_message = output.error_message ? output.error_message : "";
    if (free_result_) {
        free_result_(&output);
    }
    return rc == 0;
}

std::string SdkLoader::last_error() const {
    return last_error_;
}

std::string SdkLoader::capability_id() const {
    return plugin_info_.capability_id ? plugin_info_.capability_id : "";
}

}
