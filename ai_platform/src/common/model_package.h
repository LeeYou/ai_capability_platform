#ifndef AI_PLATFORM_MODEL_PACKAGE_H
#define AI_PLATFORM_MODEL_PACKAGE_H

#include <string>

namespace ai_platform {

struct ModelPackageValidationResult {
    bool ok = false;
    std::string manifest_path;
    std::string checksum_path;
    std::string model_file_path;
    std::string message;
};

ModelPackageValidationResult validate_model_package(const std::string& capability_id, const std::string& model_dir);

}

#endif
