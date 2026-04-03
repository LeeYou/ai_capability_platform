#include "model_package.h"

#include <filesystem>
#include <fstream>
#include <sstream>

namespace ai_platform {

namespace {

std::string trim_copy(const std::string& value) {
    std::size_t start = 0;
    while (start < value.size() && (value[start] == ' ' || value[start] == '\t' || value[start] == '\r' || value[start] == '\n')) {
        ++start;
    }

    std::size_t end = value.size();
    while (end > start && (value[end - 1] == ' ' || value[end - 1] == '\t' || value[end - 1] == '\r' || value[end - 1] == '\n')) {
        --end;
    }

    return value.substr(start, end - start);
}

bool read_manifest_field(const std::filesystem::path& manifest_path, const std::string& field_name, std::string* value) {
    std::ifstream input(manifest_path);
    if (!input.is_open()) {
        return false;
    }

    const std::string prefix = field_name + ":";
    std::string line;
    while (std::getline(input, line)) {
        const std::string trimmed = trim_copy(line);
        if (trimmed.rfind(prefix, 0) != 0) {
            continue;
        }
        *value = trim_copy(trimmed.substr(prefix.size()));
        return true;
    }

    return false;
}

}

ModelPackageValidationResult validate_model_package(const std::string& capability_id, const std::string& model_dir) {
    ModelPackageValidationResult result;

    if (model_dir.empty()) {
        result.message = "model dir is empty";
        return result;
    }

    const std::filesystem::path model_dir_path(model_dir);
    if (!std::filesystem::exists(model_dir_path)) {
        result.message = "model dir does not exist";
        return result;
    }
    if (!std::filesystem::is_directory(model_dir_path)) {
        result.message = "model dir is not a directory";
        return result;
    }

    const std::filesystem::path manifest_path = model_dir_path / "manifest.yaml";
    const std::filesystem::path checksum_path = model_dir_path / "checksum.sha256";
    result.manifest_path = manifest_path.string();
    result.checksum_path = checksum_path.string();

    if (!std::filesystem::exists(manifest_path)) {
        result.message = "manifest.yaml missing";
        return result;
    }
    if (!std::filesystem::exists(checksum_path)) {
        result.message = "checksum.sha256 missing";
        return result;
    }

    std::string manifest_capability_id;
    if (!read_manifest_field(manifest_path, "capability_id", &manifest_capability_id) || manifest_capability_id.empty()) {
        result.message = "manifest capability_id missing";
        return result;
    }
    if (manifest_capability_id != capability_id) {
        result.message = "manifest capability_id mismatch";
        return result;
    }

    std::string manifest_model_file;
    if (!read_manifest_field(manifest_path, "model_file", &manifest_model_file) || manifest_model_file.empty()) {
        result.message = "manifest model_file missing";
        return result;
    }

    const std::filesystem::path model_file_path = model_dir_path / manifest_model_file;
    result.model_file_path = model_file_path.string();
    if (!std::filesystem::exists(model_file_path)) {
        result.message = "model file missing";
        return result;
    }

    result.ok = true;
    result.message = "model package valid";
    return result;
}

}
