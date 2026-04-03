#include "plugin_manager.h"

#include "test_runtime_helpers.h"

#include <filesystem>
#include <fstream>
#include <string>

int main(int argc, char** argv) {
    ai_platform::tests::assert_true(argc >= 6, "usage: test_plugin_manager <face_detect_plugin_path> <liveness_action_plugin_path> <idcard_detect_plugin_path> <doc_classify_plugin_path> <seal_detect_plugin_path>");

    const std::filesystem::path temp_dir = std::filesystem::temp_directory_path() / "ai_platform_plugin_manager_tests";
    const std::string registry_path = ai_platform::tests::create_registry_file(temp_dir, argv[1], argv[2], argv[3], argv[4], argv[5]);
    ai_platform::tests::set_env_var("AI_PLATFORM_PLUGINS_REGISTRY_PATH", registry_path);

    ai_platform::PluginManager plugin_manager;
    ai_platform::tests::assert_true(plugin_manager.load_default_plugins(), "plugin manager should load registry plugins");
    ai_platform::tests::assert_true(plugin_manager.plugins().size() == 5, "plugin manager should load all sample capabilities");
    const auto load_diagnostics = plugin_manager.get_load_diagnostics();
    ai_platform::tests::assert_true(load_diagnostics.registry_opened, "plugin load diagnostics should mark registry opened");
    ai_platform::tests::assert_true(load_diagnostics.configured_count == 5, "plugin load diagnostics should count configured capabilities");
    ai_platform::tests::assert_true(load_diagnostics.loaded_count == 5, "plugin load diagnostics should count loaded capabilities");
    ai_platform::tests::assert_true(load_diagnostics.failures.empty(), "plugin load diagnostics should have no failures for sample plugins");

    const auto* face_detect = plugin_manager.get_plugin("face_detect");
    ai_platform::tests::assert_true(face_detect != nullptr, "face_detect plugin should exist");
    ai_platform::tests::assert_true(face_detect->instance_count == 2, "face_detect plugin should preserve instance count from registry");
    ai_platform::tests::assert_true(std::filesystem::path(face_detect->model_dir).filename().string() == "face_detect", "face_detect model dir should come from registry");

    const auto* liveness_action = plugin_manager.get_plugin("liveness_action");
    ai_platform::tests::assert_true(liveness_action != nullptr, "liveness_action plugin should exist");
    ai_platform::tests::assert_true(liveness_action->plugin_info.capability_id != nullptr, "liveness_action plugin info capability id should be available");
    ai_platform::tests::assert_true(std::string(liveness_action->plugin_info.capability_id) == "liveness_action", "liveness_action plugin info capability id should match");

    const auto* idcard_detect = plugin_manager.get_plugin("idcard_detect");
    ai_platform::tests::assert_true(idcard_detect != nullptr, "idcard_detect plugin should exist");
    ai_platform::tests::assert_true(idcard_detect->plugin_info.capability_id != nullptr, "idcard_detect plugin info capability id should be available");
    ai_platform::tests::assert_true(std::string(idcard_detect->plugin_info.capability_id) == "idcard_detect", "idcard_detect plugin info capability id should match");
    ai_platform::tests::assert_true(std::filesystem::path(idcard_detect->model_dir).filename().string() == "idcard_detect", "idcard_detect model dir should come from registry");

    const auto* doc_classify = plugin_manager.get_plugin("doc_classify");
    ai_platform::tests::assert_true(doc_classify != nullptr, "doc_classify plugin should exist");
    ai_platform::tests::assert_true(doc_classify->plugin_info.capability_id != nullptr, "doc_classify plugin info capability id should be available");
    ai_platform::tests::assert_true(std::string(doc_classify->plugin_info.capability_id) == "doc_classify", "doc_classify plugin info capability id should match");
    ai_platform::tests::assert_true(std::filesystem::path(doc_classify->model_dir).filename().string() == "doc_classify", "doc_classify model dir should come from registry");

    const auto* seal_detect = plugin_manager.get_plugin("seal_detect");
    ai_platform::tests::assert_true(seal_detect != nullptr, "seal_detect plugin should exist");
    ai_platform::tests::assert_true(seal_detect->plugin_info.capability_id != nullptr, "seal_detect plugin info capability id should be available");
    ai_platform::tests::assert_true(std::string(seal_detect->plugin_info.capability_id) == "seal_detect", "seal_detect plugin info capability id should match");
    ai_platform::tests::assert_true(std::filesystem::path(seal_detect->model_dir).filename().string() == "seal_detect", "seal_detect model dir should come from registry");

    const std::string face_detect_v2_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "face_detect", "face_detect_v2");
    const auto reload_result = plugin_manager.reload_plugin("face_detect", ai_platform::RuntimeReloadType::kModel, face_detect_v2_model_dir);
    ai_platform::tests::assert_true(reload_result.ok, "face_detect model reload should succeed");
    ai_platform::tests::assert_true(std::filesystem::path(reload_result.previous_model_dir).filename().string() == "face_detect", "reload should report previous model dir");
    ai_platform::tests::assert_true(reload_result.current_model_dir == face_detect_v2_model_dir, "reload should report current model dir");
    ai_platform::tests::assert_true(std::filesystem::path(plugin_manager.get_plugin("face_detect")->previous_model_dir).filename().string() == "face_detect", "plugin previous model dir should be preserved after reload");
    ai_platform::tests::assert_true(plugin_manager.get_plugin("face_detect")->model_dir == face_detect_v2_model_dir, "plugin model dir should update after reload");

    const std::string idcard_detect_v2_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "idcard_detect", "idcard_detect_v2");
    const auto idcard_reload_result = plugin_manager.reload_plugin("idcard_detect", ai_platform::RuntimeReloadType::kModel, idcard_detect_v2_model_dir);
    ai_platform::tests::assert_true(idcard_reload_result.ok, "idcard_detect model reload should succeed");
    ai_platform::tests::assert_true(std::filesystem::path(idcard_reload_result.previous_model_dir).filename().string() == "idcard_detect", "idcard_detect reload should report previous model dir");
    ai_platform::tests::assert_true(idcard_reload_result.current_model_dir == idcard_detect_v2_model_dir, "idcard_detect reload should report current model dir");

    const std::string doc_classify_v2_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "doc_classify", "doc_classify_v2");
    const auto doc_classify_reload_result = plugin_manager.reload_plugin("doc_classify", ai_platform::RuntimeReloadType::kModel, doc_classify_v2_model_dir);
    ai_platform::tests::assert_true(doc_classify_reload_result.ok, "doc_classify model reload should succeed");
    ai_platform::tests::assert_true(std::filesystem::path(doc_classify_reload_result.previous_model_dir).filename().string() == "doc_classify", "doc_classify reload should report previous model dir");
    ai_platform::tests::assert_true(doc_classify_reload_result.current_model_dir == doc_classify_v2_model_dir, "doc_classify reload should report current model dir");

    const std::string seal_detect_v2_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "seal_detect", "seal_detect_v2");
    const auto seal_detect_reload_result = plugin_manager.reload_plugin("seal_detect", ai_platform::RuntimeReloadType::kModel, seal_detect_v2_model_dir);
    ai_platform::tests::assert_true(seal_detect_reload_result.ok, "seal_detect model reload should succeed");
    ai_platform::tests::assert_true(std::filesystem::path(seal_detect_reload_result.previous_model_dir).filename().string() == "seal_detect", "seal_detect reload should report previous model dir");
    ai_platform::tests::assert_true(seal_detect_reload_result.current_model_dir == seal_detect_v2_model_dir, "seal_detect reload should report current model dir");

    const std::filesystem::path invalid_model_dir = std::filesystem::path(temp_dir) / "models" / "face_detect_invalid";
    std::filesystem::create_directories(invalid_model_dir);
    {
        std::ofstream checksum_output(invalid_model_dir / "checksum.sha256", std::ios::trunc);
        checksum_output << "0000000000000000000000000000000000000000000000000000000000000000  model.onnx\n";
    }
    const auto invalid_reload = plugin_manager.reload_plugin("face_detect", ai_platform::RuntimeReloadType::kModel, invalid_model_dir.string());
    ai_platform::tests::assert_true(!invalid_reload.ok, "reload with invalid model package should fail");
    ai_platform::tests::assert_true(invalid_reload.message.rfind("model package validation failed:", 0) == 0, "reload should expose model package validation failure message");

    const auto missing_reload = plugin_manager.reload_plugin("missing_capability", ai_platform::RuntimeReloadType::kModel, "models/missing");
    ai_platform::tests::assert_true(!missing_reload.ok, "missing capability reload should fail");
    ai_platform::tests::assert_true(missing_reload.message == "capability not found", "missing capability reload should expose not found message");

    return 0;
}
