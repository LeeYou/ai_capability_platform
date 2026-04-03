#include "doc_classify_sdk.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "usage: ai_sdk_doc_classify_sample <plugin_path> <model_dir> [license_path]" << std::endl;
        return 1;
    }

    ai_platform::DocClassifySdk sdk;
    const std::string license_path = argc >= 4 ? argv[3] : std::string();
    if (!sdk.initialize(argv[1], argv[2], license_path)) {
        std::cerr << sdk.last_error() << std::endl;
        if (!sdk.last_license_failure_reason().empty()) {
            std::cerr << "license_failure_reason=" << sdk.last_license_failure_reason() << std::endl;
            std::cerr << "license_failure_detail=" << sdk.last_license_failure_detail() << std::endl;
        }
        return 2;
    }

    if (sdk.capability_id() != "doc_classify") {
        std::cerr << "unexpected capability id: " << sdk.capability_id() << std::endl;
        return 3;
    }

    const auto infer_result = sdk.infer_image_base64("YWJjZA==", "jpg");
    if (!infer_result.ok) {
        std::cerr << "infer failed: " << infer_result.error_message << std::endl;
        return 4;
    }

    std::cout << infer_result.result_json << std::endl;
    return infer_result.code;
}
