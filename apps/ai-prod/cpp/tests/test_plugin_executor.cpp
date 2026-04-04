#include "plugin_executor.h"

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

std::filesystem::path CurrentBinaryDir(const char* argv0) {
    return std::filesystem::weakly_canonical(std::filesystem::path(argv0)).parent_path();
}

std::string SharedLibraryName() {
#ifdef _WIN32
    return "test_mock_ai_plugin.dll";
#elif __APPLE__
    return "libtest_mock_ai_plugin.dylib";
#else
    return "libtest_mock_ai_plugin.so";
#endif
}

void WriteText(const std::filesystem::path& path, const std::string& content) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    output << content;
}

}

int main(int argc, char** argv) {
    const auto temp_root = std::filesystem::temp_directory_path() / "ai_prod_cpp_plugin_executor_test";
    std::filesystem::remove_all(temp_root);
    const auto model_root = temp_root / "models" / "face_detect" / "v1_0_0";
    WriteText(model_root / "manifest.json", R"({"capability_name":"face_detect","model_version":"v1_0_0"})");

    const auto plugin_binary = CurrentBinaryDir(argv[0]) / SharedLibraryName();
    if (!Expect(std::filesystem::exists(plugin_binary), "test plugin library should exist")) {
        return 1;
    }

    PluginExecutor executor;
    CapabilityCatalogEntry entry;
    entry.capability_name = "face_detect";
    entry.model_root = model_root.string();
    entry.binary_path = plugin_binary.string();
    entry.pool_size = 2;
    entry.max_batch_size = 4;

    PluginExecutionResult result;
    std::string error_message;
    PluginFailureKind failure_kind = PluginFailureKind::kNone;
    if (!Expect(
            executor.Execute(
                entry,
                0,
                "json",
                "{\"image\":\"demo\"}",
                nlohmann::json::object(),
                "cpu",
                "req-cpu-1",
                &result,
                &error_message,
                &failure_kind),
            error_message.c_str())) {
        return 1;
    }
    executor.RecordLifecycleSample("face_detect", "cpu", 5.0);
    if (!Expect(result.plugin_result.value("mock", false), "plugin result should come from mock plugin")) {
        return 1;
    }
    if (!Expect(result.plugin_result.value("device", "") == "cpu", "plugin should receive cpu device")) {
        return 1;
    }
    if (!Expect(result.plugin_result.value("max_batch_size", 0) == 4, "plugin should receive configured max batch size")) {
        return 1;
    }
    if (!Expect(
            executor.Execute(
                entry,
                1,
                "image",
                "binary-cpu",
                nlohmann::json::object(),
                "cpu",
                "req-cpu-2",
                &result,
                &error_message,
                &failure_kind),
            error_message.c_str())) {
        return 1;
    }
    const auto cpu_metrics = executor.GetCapabilityMetrics("face_detect");
    if (!Expect(cpu_metrics.has_value(), "plugin executor should expose metrics for loaded capability")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["total_requests"] == 2, "cpu metrics should aggregate executed requests")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["successful_requests"] == 2, "cpu metrics should count successful requests")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["failed_requests"] == 0, "cpu metrics should count zero failed requests")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["max_batch_size"] == 4, "plugin metrics should expose max batch size")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["avg_lifecycle_time_ms"] >= (*cpu_metrics)["avg_infer_time_ms"], "plugin metrics should expose lifecycle latency")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["bindings"][0]["plugin_info"]["capability_id"] == "mock_capability", "plugin metrics should expose plugin info")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["bindings"][0]["max_batch_size"] == 4, "binding metrics should expose max batch size")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["bindings"][0]["plugin_info"]["extra_info_json"] == "{\"max_batch_size\":4}", "plugin info should expose batch metadata")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["warmup_status"] == "passed", "plugin metrics should expose successful warmup status")) {
        return 1;
    }
    if (!Expect((*cpu_metrics)["health_check_status"] == "passed", "plugin metrics should expose successful health status")) {
        return 1;
    }
    if (!Expect(!(*cpu_metrics)["last_warmup_at_utc"].is_null(), "plugin metrics should expose warmup timestamp")) {
        return 1;
    }
    if (!Expect(!(*cpu_metrics)["last_health_check_at_utc"].is_null(), "plugin metrics should expose health timestamp")) {
        return 1;
    }

    entry.model_root = (temp_root / "models" / "face_detect" / "v2_0_0").string();
    entry.max_batch_size = 3;
    WriteText(std::filesystem::path(entry.model_root) / "manifest.json", R"({"capability_name":"face_detect","model_version":"v2_0_0"})");
    executor.SyncEntries({entry});
    if (!Expect(
            executor.Execute(
                entry,
                1,
                "image",
                "binary",
                nlohmann::json::object(),
                "gpu",
                "req-gpu-1",
                &result,
                &error_message,
                &failure_kind),
            error_message.c_str())) {
        return 1;
    }
    executor.RecordLifecycleSample("face_detect", "gpu", 4.0);
    if (!Expect(result.plugin_result.value("device", "") == "cuda", "plugin should receive gpu device")) {
        return 1;
    }
    if (!Expect(result.plugin_result.value("model_dir", "") == entry.model_root, "sync should refresh model root")) {
        return 1;
    }
    const auto gpu_metrics = executor.GetCapabilityMetrics("face_detect");
    if (!Expect(gpu_metrics.has_value(), "plugin executor should expose metrics after sync reload")) {
        return 1;
    }
    if (!Expect((*gpu_metrics)["bindings"].size() == 1, "sync should drop old binding metrics for replaced capability")) {
        return 1;
    }
    if (!Expect((*gpu_metrics)["bindings"][0]["device"] == "gpu", "binding metrics should expose device")) {
        return 1;
    }
    if (!Expect((*gpu_metrics)["bindings"][0]["max_batch_size"] == 3, "binding metrics should refresh max batch size")) {
        return 1;
    }
    if (!Expect((*gpu_metrics)["bindings"][0]["plugin_info"]["current_device"] == "gpu", "plugin info should expose current device")) {
        return 1;
    }

    CapabilityCatalogEntry failing_entry = entry;
    failing_entry.capability_name = "warmup_fail";
    failing_entry.model_root = (temp_root / "models" / "warmup_fail" / "v1_0_0").string();
    WriteText(std::filesystem::path(failing_entry.model_root) / "manifest.json", R"({"capability_name":"warmup_fail","model_version":"v1_0_0"})");
    if (!Expect(
            !executor.Execute(
                failing_entry,
                0,
                "json",
                "{\"image\":\"demo\"}",
                nlohmann::json::object(),
                "cpu",
                "req-warmup-fail",
                &result,
                &error_message,
                &failure_kind),
            "warmup failure should reject plugin load")) {
        return 1;
    }
    if (!Expect(error_message == "能力插件预热失败。", "warmup failure should return lifecycle error")) {
        return 1;
    }
    if (!Expect(failure_kind == PluginFailureKind::kLifecycleFailure, "warmup failure should classify as lifecycle failure")) {
        return 1;
    }

    failing_entry.capability_name = "health_fail";
    failing_entry.model_root = (temp_root / "models" / "health_fail" / "v1_0_0").string();
    WriteText(std::filesystem::path(failing_entry.model_root) / "manifest.json", R"({"capability_name":"health_fail","model_version":"v1_0_0"})");
    if (!Expect(
            !executor.Execute(
                failing_entry,
                0,
                "json",
                "{\"image\":\"demo\"}",
                nlohmann::json::object(),
                "cpu",
                "req-health-fail",
                &result,
                &error_message,
                &failure_kind),
            "health check failure should reject plugin load")) {
        return 1;
    }
    if (!Expect(error_message == "能力插件健康检查失败。", "health failure should return lifecycle error")) {
        return 1;
    }

    entry.capability_name = "gpu_fallback";
    entry.model_root = (temp_root / "models" / "gpucheckfail" / "v1_0_0").string();
    entry.max_batch_size = 2;
    WriteText(std::filesystem::path(entry.model_root) / "manifest.json", R"({"capability_name":"gpu_fallback","model_version":"v1_0_0"})");
    if (!Expect(
            !executor.Execute(
                entry,
                0,
                "json",
                "{\"image\":\"demo\"}",
                nlohmann::json::object(),
                "gpu",
                "req-gpu-fail",
                &result,
                &error_message,
                &failure_kind),
            "gpu health failure should reject gpu binding")) {
        return 1;
    }
    if (!Expect(failure_kind == PluginFailureKind::kLifecycleFailure, "gpu health failure should classify as lifecycle failure")) {
        return 1;
    }
    if (!Expect(error_message == "能力插件健康检查失败。", "gpu health failure should surface lifecycle error")) {
        return 1;
    }
    if (!Expect(
            executor.Execute(
                entry,
                0,
                "json",
                "{\"image\":\"demo\"}",
                nlohmann::json::object(),
                "cpu",
                "req-cpu-fallback",
                &result,
                &error_message,
                &failure_kind),
            error_message.c_str())) {
        return 1;
    }
    executor.RecordFallback("gpu_fallback", "cpu", "能力插件健康检查失败。");
    executor.RecordLifecycleSample("gpu_fallback", "cpu", 6.0);
    const auto fallback_metrics = executor.GetCapabilityMetrics("gpu_fallback");
    if (!Expect(fallback_metrics.has_value(), "fallback metrics should exist after cpu execution")) {
        return 1;
    }
    if (!Expect((*fallback_metrics)["fallback_count"] == 1, "fallback metrics should count recorded fallback")) {
        return 1;
    }
    if (!Expect((*fallback_metrics)["last_fallback_reason"] == "能力插件健康检查失败。", "fallback metrics should expose last fallback reason")) {
        return 1;
    }
    if (!Expect((*fallback_metrics)["avg_lifecycle_time_ms"] >= (*fallback_metrics)["avg_infer_time_ms"], "fallback metrics should expose lifecycle latency")) {
        return 1;
    }

    std::filesystem::remove_all(temp_root);
    return 0;
}
