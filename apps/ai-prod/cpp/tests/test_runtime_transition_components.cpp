#include "revision_store.h"
#include "runtime_resource_scanner.h"

#include <filesystem>
#include <fstream>
#include <iostream>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

void WriteText(const std::filesystem::path& path, const std::string& content) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    output << content;
}

}

int main() {
    const auto temp_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_transition_components";
    const auto host_root = temp_root / "host";
    const auto image_root = temp_root / "image";
    const auto database_path = temp_root / "data" / "ai_prod.db";
    std::filesystem::remove_all(temp_root);

    WriteText(
        host_root / "models" / "face_detect" / "v2_0_0" / "manifest.json",
        R"({"capability_name":"face_detect","model_version":"v2_0_0","backend_type":"onnxruntime","max_batch_size":8,"queue_wait_timeout_ms":260})");
    WriteText(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "manifest" / "manifest.json",
        R"({"capability_name":"face_detect","target_name":"linux_x86_64","build_mode":"release","instance_count":3,"max_pending_request_count":6})");
    WriteText(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "lib" / "libface_detect.so",
        "binary");
    WriteText(
        image_root / "models" / "ocr" / "v1_0_0" / "manifest.json",
        R"({"capability_name":"ocr","model_version":"v1_0_0","backend_type":"onnxruntime"})");
    WriteText(
        image_root / "libs" / "linux_x86_64" / "ocr" / "manifest" / "manifest.json",
        R"({"capability_name":"ocr","target_name":"linux_x86_64","build_mode":"template"})");
    WriteText(
        image_root / "libs" / "linux_x86_64" / "ocr" / "lib" / "libocr.so",
        "binary");

    const auto scan_result = RuntimeResourceScanner::ResolveSources(
        host_root.string(),
        image_root.string(),
        "linux_x86_64");
    if (!Expect(scan_result.capabilities.size() == 2, "scanner should merge host and image capabilities")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").active_source == "host", "host capability should win")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("ocr").active_source == "image", "image capability should be used when host missing")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").max_batch_size == 8, "scanner should keep max batch size")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").instance_count == 3, "scanner should keep instance count")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").queue_wait_timeout_ms == 260, "scanner should keep queue wait timeout")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").max_pending_request_count == 6, "scanner should keep max pending request count")) {
        return 1;
    }
    const auto serialized_capability = SerializeRuntimeCapabilityRecord(scan_result.capabilities.at("face_detect"));
    std::string deserialize_error;
    const auto deserialized_capability = DeserializeRuntimeCapabilityRecord(serialized_capability, &deserialize_error);
    if (!Expect(deserialized_capability.has_value(), deserialize_error.c_str())) {
        return 1;
    }
    if (!Expect(deserialized_capability->model_version == "v2_0_0", "serialized capability should keep model version")) {
        return 1;
    }
    if (!Expect(deserialized_capability->binary_path == scan_result.capabilities.at("face_detect").binary_path, "serialized capability should keep binary path")) {
        return 1;
    }
    if (!Expect(deserialized_capability->max_batch_size == 8, "serialized capability should keep max batch size")) {
        return 1;
    }
    if (!Expect(deserialized_capability->instance_count == 3, "serialized capability should keep instance count")) {
        return 1;
    }
    if (!Expect(deserialized_capability->queue_wait_timeout_ms == 260, "serialized capability should keep queue wait timeout")) {
        return 1;
    }
    if (!Expect(deserialized_capability->max_pending_request_count == 6, "serialized capability should keep max pending request count")) {
        return 1;
    }

    RevisionStore revision_store(database_path.string());
    std::string error_message;
    if (!Expect(revision_store.EnsureSchema(&error_message), error_message.c_str())) {
        return 1;
    }

    const auto revision = revision_store.CreateRevision(
        "token-demo",
        "reload",
        "active",
        scan_result.source_summary,
        nlohmann::json::array({"face_detect", "ocr"}),
        true,
        nlohmann::json{{"license_status", {{"valid", true}, {"reason", "ok"}}}},
        std::nullopt,
        &error_message);
    if (!Expect(revision.has_value(), error_message.c_str())) {
        return 1;
    }

    const auto operation = revision_store.CreateOperation(
        "reload",
        "completed",
        nlohmann::json{{"active_capability_count", 2}},
        revision->id,
        &error_message);
    if (!Expect(operation.has_value(), error_message.c_str())) {
        return 1;
    }

    const auto loaded_revision = revision_store.GetRevision(revision->id, &error_message);
    if (!Expect(loaded_revision.has_value(), error_message.c_str())) {
        return 1;
    }
    if (!Expect(loaded_revision->capability_names.size() == 2, "loaded revision should keep capability names")) {
        return 1;
    }
    if (!Expect(loaded_revision->action == "reload", "loaded revision should keep action")) {
        return 1;
    }

    std::filesystem::remove_all(temp_root);
    return 0;
}
