#include "pool_manager.h"
#include "plugin_manager.h"
#include "reload_controller.h"

#include "test_runtime_helpers.h"

#include <filesystem>
#include <algorithm>
#include <string>

int main(int argc, char** argv) {
    ai_platform::tests::assert_true(argc >= 6, "usage: test_reload_controller <face_detect_plugin_path> <liveness_action_plugin_path> <idcard_detect_plugin_path> <doc_classify_plugin_path> <seal_detect_plugin_path>");

    const std::filesystem::path temp_dir = std::filesystem::temp_directory_path() / "ai_platform_reload_controller_tests";
    const std::string registry_path = ai_platform::tests::create_registry_file(temp_dir, argv[1], argv[2], argv[3], argv[4], argv[5]);
    ai_platform::tests::set_env_var("AI_PLATFORM_PLUGINS_REGISTRY_PATH", registry_path);

    ai_platform::PluginManager plugin_manager;
    ai_platform::tests::assert_true(plugin_manager.load_default_plugins(), "plugin manager should load sample plugins for reload controller tests");

    ai_platform::PoolManager pool_manager;
    pool_manager.rebuild(plugin_manager.plugins());
    ai_platform::ReloadController reload_controller(plugin_manager, pool_manager);

    const std::string face_detect_reloaded_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "face_detect", "face_detect_reloaded");
    const auto reload_result = reload_controller.reload_capability("face_detect", ai_platform::RuntimeReloadType::kModel, face_detect_reloaded_model_dir);
    ai_platform::tests::assert_true(reload_result.ok, "reload controller should reload face_detect model successfully");
    ai_platform::tests::assert_true(reload_result.current_stage == "complete", "successful reload should finish at complete stage");
    ai_platform::tests::assert_true(reload_result.current_model_dir == face_detect_reloaded_model_dir, "successful reload should update current model dir");
    ai_platform::tests::assert_true(!reload_result.reloaded_capability_ids.empty() && reload_result.reloaded_capability_ids.front() == "face_detect", "successful reload should record reloaded capability");

    const auto rollback_result = reload_controller.rollback_capability("face_detect");
    ai_platform::tests::assert_true(rollback_result.ok, "rollback should succeed after model reload");
    ai_platform::tests::assert_true(rollback_result.rollback_performed, "rollback should report rollback performed");
    ai_platform::tests::assert_true(std::filesystem::path(rollback_result.current_model_dir).filename().string() == "face_detect", "rollback should restore original model dir");

    const std::string idcard_detect_reloaded_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "idcard_detect", "idcard_detect_reloaded");
    const auto idcard_reload_result = reload_controller.reload_capability("idcard_detect", ai_platform::RuntimeReloadType::kModel, idcard_detect_reloaded_model_dir);
    ai_platform::tests::assert_true(idcard_reload_result.ok, "reload controller should reload idcard_detect model successfully");
    ai_platform::tests::assert_true(idcard_reload_result.current_stage == "complete", "successful idcard_detect reload should finish at complete stage");
    ai_platform::tests::assert_true(idcard_reload_result.current_model_dir == idcard_detect_reloaded_model_dir, "successful idcard_detect reload should update current model dir");

    const auto idcard_rollback_result = reload_controller.rollback_capability("idcard_detect");
    ai_platform::tests::assert_true(idcard_rollback_result.ok, "idcard_detect rollback should succeed after model reload");
    ai_platform::tests::assert_true(std::filesystem::path(idcard_rollback_result.current_model_dir).filename().string() == "idcard_detect", "idcard_detect rollback should restore original model dir");

    const std::string doc_classify_reloaded_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "doc_classify", "doc_classify_reloaded");
    const auto doc_classify_reload_result = reload_controller.reload_capability("doc_classify", ai_platform::RuntimeReloadType::kModel, doc_classify_reloaded_model_dir);
    ai_platform::tests::assert_true(doc_classify_reload_result.ok, "reload controller should reload doc_classify model successfully");
    ai_platform::tests::assert_true(doc_classify_reload_result.current_stage == "complete", "successful doc_classify reload should finish at complete stage");
    ai_platform::tests::assert_true(doc_classify_reload_result.current_model_dir == doc_classify_reloaded_model_dir, "successful doc_classify reload should update current model dir");

    const auto doc_classify_rollback_result = reload_controller.rollback_capability("doc_classify");
    ai_platform::tests::assert_true(doc_classify_rollback_result.ok, "doc_classify rollback should succeed after model reload");
    ai_platform::tests::assert_true(std::filesystem::path(doc_classify_rollback_result.current_model_dir).filename().string() == "doc_classify", "doc_classify rollback should restore original model dir");

    const std::string seal_detect_reloaded_model_dir = ai_platform::tests::create_model_package(temp_dir / "models", "seal_detect", "seal_detect_reloaded");
    const auto seal_detect_reload_result = reload_controller.reload_capability("seal_detect", ai_platform::RuntimeReloadType::kModel, seal_detect_reloaded_model_dir);
    ai_platform::tests::assert_true(seal_detect_reload_result.ok, "reload controller should reload seal_detect model successfully");
    ai_platform::tests::assert_true(seal_detect_reload_result.current_stage == "complete", "successful seal_detect reload should finish at complete stage");
    ai_platform::tests::assert_true(seal_detect_reload_result.current_model_dir == seal_detect_reloaded_model_dir, "successful seal_detect reload should update current model dir");

    const auto seal_detect_rollback_result = reload_controller.rollback_capability("seal_detect");
    ai_platform::tests::assert_true(seal_detect_rollback_result.ok, "seal_detect rollback should succeed after model reload");
    ai_platform::tests::assert_true(std::filesystem::path(seal_detect_rollback_result.current_model_dir).filename().string() == "seal_detect", "seal_detect rollback should restore original model dir");

    const auto failed_reload = reload_controller.reload_capability("face_detect", ai_platform::RuntimeReloadType::kModel, "__test_fail_reload__:face_detect");
    ai_platform::tests::assert_true(!failed_reload.ok, "reload controller should report plugin reload failure");
    ai_platform::tests::assert_true(failed_reload.rolled_back, "failed reload should keep rolled_back flag for preserved previous state");
    ai_platform::tests::assert_true(!failed_reload.reload_failure_details.empty(), "failed reload should expose reload failure details");
    ai_platform::tests::assert_true(failed_reload.reload_failure_details.front().reload_failed_stage == "reload", "failed reload detail should identify reload stage");

    const auto missing_rollback = reload_controller.rollback_capability("missing_capability");
    ai_platform::tests::assert_true(!missing_rollback.ok, "rollback for missing capability should fail");
    ai_platform::tests::assert_true(missing_rollback.rollback_reason == "capability_not_found", "missing capability rollback should report capability_not_found reason");

    const std::filesystem::path shared_reloaded_model_root = temp_dir / "models" / "shared_reloaded";
    const std::string shared_reloaded_model_dir = shared_reloaded_model_root.string();
    ai_platform::tests::create_model_package(shared_reloaded_model_root, "face_detect");
    ai_platform::tests::create_model_package(shared_reloaded_model_root, "liveness_action");
    ai_platform::tests::create_model_package(shared_reloaded_model_root, "idcard_detect");
    ai_platform::tests::create_model_package(shared_reloaded_model_root, "doc_classify");
    ai_platform::tests::create_model_package(shared_reloaded_model_root, "seal_detect");
    const auto reload_all_result = reload_controller.reload_all_capabilities(ai_platform::RuntimeReloadType::kModel, shared_reloaded_model_dir);
    ai_platform::tests::assert_true(reload_all_result.ok, "reload all should succeed for sample plugins");
    ai_platform::tests::assert_true(reload_all_result.reloaded_all, "reload all should mark reloaded_all flag");
    ai_platform::tests::assert_true(reload_all_result.reloaded_capability_ids.size() == 5, "reload all should include all sample capabilities");
    ai_platform::tests::assert_true(std::find(reload_all_result.reloaded_capability_ids.begin(), reload_all_result.reloaded_capability_ids.end(), "idcard_detect") != reload_all_result.reloaded_capability_ids.end(), "reload all should include idcard_detect");
    ai_platform::tests::assert_true(std::find(reload_all_result.reloaded_capability_ids.begin(), reload_all_result.reloaded_capability_ids.end(), "doc_classify") != reload_all_result.reloaded_capability_ids.end(), "reload all should include doc_classify");
    ai_platform::tests::assert_true(std::find(reload_all_result.reloaded_capability_ids.begin(), reload_all_result.reloaded_capability_ids.end(), "seal_detect") != reload_all_result.reloaded_capability_ids.end(), "reload all should include seal_detect");

    return 0;
}
