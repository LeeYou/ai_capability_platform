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

std::string BuildModelManifest(
    const std::filesystem::path& model_root,
    const std::string& capability_name,
    const std::string& model_version,
    int max_batch_size,
    int min_batch_size = 1,
    int batch_wait_timeout_ms = -1,
    int queue_wait_timeout_ms = -1,
    int infer_timeout_ms = -1,
    int estimated_avg_infer_time_ms = -1,
    int p95_infer_time_ms = -1,
    int max_concurrent_requests = -1,
    int capability_priority = 100,
    bool supports_concurrent_infer = true,
    bool allow_resource_sharing = false) {
    const auto preprocess_path = model_root / "preprocess.json";
    const auto labels_path = model_root / "labels.json";
    const auto validation_path = model_root / "validation" / "acceptance_checklist.json";
    const auto delivery_metadata_path = model_root / "delivery_metadata.json";
    const auto runtime_contract_path = model_root / "runtime_contract.json";
    WriteText(preprocess_path, R"({"input_type":"image","resize":{"width":640,"height":640},"normalize":{"mean":[0.5],"std":[0.5]}})");
    WriteText(labels_path, R"({"labels":["ok","ng"]})");
    WriteText(validation_path, R"({"required_cases":["acceptance_check"]})");
    WriteText(delivery_metadata_path, R"({"ai_builder":{"manifest_schema_path":"apps/shared/schemas/manifest_model.json"}})");
    const nlohmann::json runtime_contract = {
        {"task_type", "detection"},
        {"annotation_schema", {{"type", "object"}}},
        {"template_bundle", {{"name", capability_name}}},
        {"model_files", nlohmann::json::array({"model.onnx"})},
        {"runtime_inputs", {{"preprocess_path", preprocess_path.string()}, {"labels_path", labels_path.string()}}},
    };
    WriteText(runtime_contract_path, runtime_contract.dump());
    nlohmann::json manifest = {
        {"capability_name", capability_name},
        {"task_type", "detection"},
        {"model_version", model_version},
        {"source_train_task_id", 1},
        {"task_name", capability_name + "_task"},
        {"backend_type", "onnxruntime"},
        {"artifact_path", model_root.string()},
        {"status", "ready"},
        {"checksum", capability_name + "-" + model_version + "-checksum"},
        {"preprocessing", {{"input_type", "image"}, {"resize", {{"width", 640}, {"height", 640}}}, {"normalize", {{"mean", nlohmann::json::array({0.5})}, {"std", nlohmann::json::array({0.5})}}}}},
        {"thresholds", {{"score_threshold", 0.5}, {"nms_threshold", 0.45}}},
        {"labels", nlohmann::json::array({"ok", "ng"})},
        {"validation", {{"artifacts", nlohmann::json::array({"preprocess.json", "labels.json", "validation/acceptance_checklist.json", "delivery_metadata.json", "runtime_contract.json"})}}},
        {"runtime_contract", runtime_contract},
        {"delivery_metadata", {{"ai_test", {{"task_type", "acceptance"}}}, {"ai_builder", {{"manifest_schema_path", "apps/shared/schemas/manifest_model.json"}}}, {"training_summary", {{"backend_type", "onnxruntime"}}}}},
        {"device_mode", "gpu/cpu"},
        {"capability_priority", capability_priority},
        {"max_batch_size", max_batch_size},
        {"min_batch_size", min_batch_size},
        {"batch_wait_timeout_ms", batch_wait_timeout_ms},
        {"queue_wait_timeout_ms", queue_wait_timeout_ms},
        {"infer_timeout_ms", infer_timeout_ms},
        {"estimated_avg_infer_time_ms", estimated_avg_infer_time_ms},
        {"p95_infer_time_ms", p95_infer_time_ms},
        {"max_concurrent_requests", max_concurrent_requests},
        {"supports_concurrent_infer", supports_concurrent_infer},
        {"allow_resource_sharing", allow_resource_sharing},
    };
    return manifest.dump();
}

std::string BuildPluginManifest(
    const std::string& capability_name,
    const std::string& model_version,
    const std::string& target_name,
    int instance_count,
    int max_pending_request_count,
    const std::string& build_mode = "native") {
    return nlohmann::json{
        {"capability_name", capability_name},
        {"model_version", model_version},
        {"target_name", target_name},
        {"artifact_format", "so"},
        {"build_mode", build_mode},
        {"toolchain_name", "cmake-native"},
        {"jni_enabled", false},
        {"customer_code", "cust_prod"},
        {"issue_record_id", 1},
        {"dependency_summary", {{"runtime", "onnxruntime"}, {"abi", "cxx17"}, {"license_required", true}, {"build_params_controlled", true}}},
        {"instance_count", instance_count},
        {"max_pending_request_count", max_pending_request_count},
    }.dump();
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
        BuildModelManifest(host_root / "models" / "face_detect" / "v2_0_0", "face_detect", "v2_0_0", 8, 2, 35, 260, 900, 45, 80, 3, 120, true, true));
    WriteText(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "manifest" / "manifest.json",
        BuildPluginManifest("face_detect", "v2_0_0", "linux_x86_64", 3, 6));
    WriteText(
        host_root / "libs" / "linux_x86_64" / "face_detect" / "lib" / "libface_detect.so",
        "binary");
    WriteText(
        image_root / "models" / "ocr" / "v1_0_0" / "manifest.json",
        BuildModelManifest(image_root / "models" / "ocr" / "v1_0_0", "ocr", "v1_0_0", 1));
    WriteText(
        image_root / "libs" / "linux_x86_64" / "ocr" / "manifest" / "manifest.json",
        BuildPluginManifest("ocr", "v1_0_0", "linux_x86_64", 1, 0));
    WriteText(
        image_root / "libs" / "linux_x86_64" / "ocr" / "lib" / "libocr.so",
        "binary");
    WriteText(
        host_root / "models" / "broken_cap" / "v1_0_0" / "manifest.json",
        BuildModelManifest(host_root / "models" / "broken_cap" / "v1_0_0", "broken_cap", "v1_0_0", 2));
    WriteText(
        host_root / "libs" / "linux_x86_64" / "broken_cap" / "manifest" / "manifest.json",
        BuildPluginManifest("broken_cap", "v9_9_9", "linux_x86_64", 1, 0));
    WriteText(
        host_root / "libs" / "linux_x86_64" / "broken_cap" / "lib" / "libbroken_cap.so",
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
    if (!Expect(scan_result.source_summary["invalid_capability_failures"].size() == 1, "scanner should record invalid capability contract failures")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").max_batch_size == 8, "scanner should keep max batch size")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").batch_wait_timeout_ms == 35, "scanner should keep batch wait timeout")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").min_batch_size == 2, "scanner should keep min batch size")) {
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
    if (!Expect(scan_result.capabilities.at("face_detect").capability_priority == 120, "scanner should keep capability priority")) {
        return 1;
    }
    if (!Expect(scan_result.capabilities.at("face_detect").allow_resource_sharing, "scanner should keep resource sharing")) {
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
    if (!Expect(deserialized_capability->batch_wait_timeout_ms == 35, "serialized capability should keep batch wait timeout")) {
        return 1;
    }
    if (!Expect(deserialized_capability->min_batch_size == 2, "serialized capability should keep min batch size")) {
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
    if (!Expect(deserialized_capability->capability_priority == 120, "serialized capability should keep capability priority")) {
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
