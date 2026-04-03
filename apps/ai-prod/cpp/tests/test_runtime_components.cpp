#include "capability_catalog.h"
#include "instance_pool.h"

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

}

int main() {
    const std::filesystem::path snapshot_path =
        std::filesystem::temp_directory_path() / "ai_prod_cpp_runtime_components_snapshot.json";
    {
        std::ofstream snapshot_output(snapshot_path);
        snapshot_output
            << "{"
            << "\"revision_id\":12,"
            << "\"capabilities\":["
            << "{"
            << "\"capability_name\":\"face_detect\","
            << "\"plugin_target\":\"linux_x86_64\","
            << "\"model_version\":\"v1_0_0\","
            << "\"backend_type\":\"onnxruntime\","
            << "\"active_source\":\"host\","
            << "\"device_mode\":\"gpu/cpu\","
            << "\"pool_size\":2,"
            << "\"revision_id\":12"
            << "},"
            << "{"
            << "\"capability_name\":\"ocr\","
            << "\"plugin_target\":\"linux_x86_64\","
            << "\"model_version\":\"v2_0_0\","
            << "\"backend_type\":\"onnxruntime\","
            << "\"active_source\":\"image\","
            << "\"device_mode\":\"cpu\","
            << "\"pool_size\":1,"
            << "\"revision_id\":12"
            << "}"
            << "]"
            << "}";
    }

    CapabilityCatalog catalog(snapshot_path.string());
    if (!Expect(catalog.RefreshIfNeeded(60), "catalog should load snapshot")) {
        return 1;
    }
    if (!Expect(catalog.GetRevisionId() == 12, "catalog revision mismatch")) {
        return 1;
    }
    const auto items = catalog.ListEntries();
    if (!Expect(items.size() == 2, "catalog item count mismatch")) {
        return 1;
    }
    const auto face_detect = catalog.GetEntry("face_detect");
    if (!Expect(face_detect.has_value(), "face_detect entry missing")) {
        return 1;
    }
    if (!Expect(face_detect->pool_size == 2, "face_detect pool size mismatch")) {
        return 1;
    }

    InstancePool pool;
    pool.Reset("face_detect", 2, true);
    if (!Expect(pool.GetTotalSize() == 2, "instance pool size mismatch")) {
        return 1;
    }
    const auto lease = pool.Acquire();
    if (!Expect(lease.has_value(), "instance pool acquire should succeed")) {
        return 1;
    }
    if (!Expect(pool.GetBusyCount() == 1, "busy count should increment")) {
        return 1;
    }
    if (!Expect(pool.Release(lease->slot_index), "instance release should succeed")) {
        return 1;
    }
    if (!Expect(pool.GetBusyCount() == 0, "busy count should return to zero")) {
        return 1;
    }

    std::filesystem::remove(snapshot_path);
    return 0;
}
