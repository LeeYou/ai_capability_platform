#include "liveness_action_dll.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: liveness_action_dll_sample <plugin_path> <model_dir> [license_path]" << std::endl;
        return 1;
    }

    const char* license_path = argc >= 4 ? argv[3] : "";
    if (ai_liveness_action_initialize(argv[1], argv[2], license_path) != 0) {
        std::cerr << "initialize failed" << std::endl;
        if (ai_liveness_action_last_license_failure_reason() != nullptr) {
            std::cerr << "license_failure_reason=" << ai_liveness_action_last_license_failure_reason() << std::endl;
            std::cerr << "license_failure_detail="
                      << (ai_liveness_action_last_license_failure_detail() ? ai_liveness_action_last_license_failure_detail() : "")
                      << std::endl;
        }
        return 2;
    }

    if (std::string(ai_liveness_action_capability_id()) != "liveness_action") {
        std::cerr << "unexpected capability id" << std::endl;
        ai_liveness_action_shutdown();
        return 3;
    }

    const auto result = ai_liveness_action_infer_base64("YWJjZA==", "mp4", "blink");
    if (result.code != 0) {
        std::cerr << (result.error_message ? result.error_message : "infer failed") << std::endl;
        ai_liveness_action_shutdown();
        return 4;
    }

    std::cout << result.result_json << std::endl;
    ai_liveness_action_shutdown();
    return 0;
}
