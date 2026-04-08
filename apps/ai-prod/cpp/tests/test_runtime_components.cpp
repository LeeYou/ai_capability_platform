#include "capability_catalog.h"
#include "instance_pool.h"
#include "runtime_state_machine.h"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>

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
            << "\"capability_priority\":150,"
            << "\"pool_size\":2,"
            << "\"max_batch_size\":8,"
            << "\"min_batch_size\":2,"
            << "\"batch_wait_timeout_ms\":35,"
            << "\"queue_wait_timeout_ms\":260,"
            << "\"max_pending_request_count\":6,"
            << "\"infer_timeout_ms\":900,"
            << "\"estimated_avg_infer_time_ms\":45,"
            << "\"p95_infer_time_ms\":80,"
            << "\"max_concurrent_requests\":3,"
            << "\"supports_concurrent_infer\":true,"
            << "\"allow_resource_sharing\":true,"
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
            << "\"max_batch_size\":2,"
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
    if (!Expect(face_detect->max_batch_size == 8, "face_detect max batch size mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->min_batch_size == 2, "face_detect min batch size mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->batch_wait_timeout_ms == 35, "face_detect batch wait timeout mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->queue_wait_timeout_ms == 260, "face_detect queue wait timeout mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->max_pending_request_count == 6, "face_detect max pending request count mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->capability_priority == 150, "face_detect capability priority mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->infer_timeout_ms == 900, "face_detect infer timeout mismatch")) {
        return 1;
    }
    if (!Expect(face_detect->allow_resource_sharing, "face_detect resource sharing mismatch")) {
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

    const auto draining_lease = pool.Acquire();
    if (!Expect(draining_lease.has_value(), "instance pool acquire before drain should succeed")) {
        return 1;
    }
    pool.BeginDrain();
    if (!Expect(pool.IsDraining(), "instance pool should enter draining state")) {
        return 1;
    }
    if (!Expect(!pool.Acquire().has_value(), "instance pool should reject new acquire during drain")) {
        return 1;
    }
    std::thread release_thread([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        pool.Release(draining_lease->slot_index);
    });
    if (!Expect(pool.WaitForIdle(std::chrono::milliseconds(500)), "instance pool should become idle during drain")) {
        release_thread.join();
        return 1;
    }
    release_thread.join();
    pool.EndDrain();
    if (!Expect(!pool.IsDraining(), "instance pool should leave draining state")) {
        return 1;
    }
    if (!Expect(pool.Acquire().has_value(), "instance pool should recover after drain")) {
        return 1;
    }
    if (!Expect(pool.GetBusyRejectCount() == 0, "busy reject count should stay zero without rejection")) {
        return 1;
    }

    InstancePool queue_pool;
    queue_pool.Reset("ocr", 1, false);
    const auto queue_holder = queue_pool.Acquire();
    if (!Expect(queue_holder.has_value(), "queue pool initial acquire should succeed")) {
        return 1;
    }
    std::thread queue_release_thread([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(40));
        queue_pool.Release(queue_holder->slot_index);
    });
    const auto queued_acquire = queue_pool.AcquireWithWait(std::chrono::milliseconds(200), 2);
    if (!Expect(queued_acquire.status == InstanceAcquireStatus::kAcquired, "queued acquire should eventually succeed")) {
        queue_release_thread.join();
        return 1;
    }
    if (!Expect(queued_acquire.queue_wait_ms >= 20, "queued acquire should record wait time")) {
        queue_release_thread.join();
        return 1;
    }
    if (!Expect(queue_pool.GetQueuedRequestCount() == 1, "queue pool should count queued success")) {
        queue_release_thread.join();
        return 1;
    }
    if (!Expect(queue_pool.Release(queued_acquire.item->slot_index), "queued acquire release should succeed")) {
        queue_release_thread.join();
        return 1;
    }
    queue_release_thread.join();

    const auto timeout_holder = queue_pool.Acquire();
    if (!Expect(timeout_holder.has_value(), "timeout holder acquire should succeed")) {
        return 1;
    }
    const auto timed_out = queue_pool.AcquireWithWait(std::chrono::milliseconds(20), 1);
    if (!Expect(timed_out.status == InstanceAcquireStatus::kTimedOut, "queued acquire should time out when slot stays busy")) {
        return 1;
    }
    if (!Expect(queue_pool.GetQueueTimeoutCount() == 1, "queue timeout count should increment")) {
        return 1;
    }
    if (!Expect(queue_pool.GetBusyRejectCount() == 1, "busy reject count should include timed out queue")) {
        return 1;
    }
    if (!Expect(queue_pool.Release(timeout_holder->slot_index), "timeout holder release should succeed")) {
        return 1;
    }

    const auto deadline_holder = queue_pool.Acquire();
    if (!Expect(deadline_holder.has_value(), "deadline holder acquire should succeed")) {
        return 1;
    }
    const auto deadline_exceeded = queue_pool.AcquireWithWait(
        std::chrono::milliseconds(100),
        1,
        std::chrono::milliseconds(10));
    if (!Expect(deadline_exceeded.status == InstanceAcquireStatus::kDeadlineExceeded, "queued acquire should stop at request deadline")) {
        return 1;
    }
    if (!Expect(deadline_exceeded.deadline_exceeded, "deadline exceeded result should mark deadline flag")) {
        return 1;
    }
    if (!Expect(queue_pool.GetDeadlineExceededCount() == 1, "deadline exceeded count should increment")) {
        return 1;
    }
    if (!Expect(queue_pool.Release(deadline_holder->slot_index), "deadline holder release should succeed")) {
        return 1;
    }

    RuntimeStateMachine state_machine;
    std::string state_error;
    if (!Expect(
            state_machine.TransitionTo(RuntimeLifecycleState::kBootstrapping, &state_error),
            "runtime state machine should enter bootstrapping")) {
        return 1;
    }
    if (!Expect(
            state_machine.TransitionTo(RuntimeLifecycleState::kReady, &state_error),
            "runtime state machine should enter ready")) {
        return 1;
    }
    if (!Expect(
            state_machine.TransitionTo(RuntimeLifecycleState::kDraining, &state_error),
            "runtime state machine should enter draining")) {
        return 1;
    }
    if (!Expect(
            state_machine.TransitionTo(RuntimeLifecycleState::kTransitioning, &state_error),
            "runtime state machine should enter transitioning")) {
        return 1;
    }
    if (!Expect(
            state_machine.TransitionTo(RuntimeLifecycleState::kReady, &state_error),
            "runtime state machine should return to ready")) {
        return 1;
    }
    if (!Expect(
            !state_machine.TransitionTo(RuntimeLifecycleState::kBootstrapping, &state_error),
            "runtime state machine should reject invalid transition")) {
        return 1;
    }
    state_machine.MarkError("transition failed");
    if (!Expect(state_machine.GetStateName() == "error", "runtime state machine should enter error")) {
        return 1;
    }
    if (!Expect(state_machine.GetLastError() == "transition failed", "runtime state machine should record last error")) {
        return 1;
    }

    std::filesystem::remove(snapshot_path);
    return 0;
}
