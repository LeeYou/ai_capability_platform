#include "resource_orchestrator.h"

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
    ResourceOrchestratorCapabilityState state;
    state.entry.capability_name = "face_detect";
    state.entry.capability_priority = 150;
    state.entry.max_batch_size = 4;
    state.entry.min_batch_size = 2;
    state.entry.max_concurrent_requests = 3;
    state.entry.allow_resource_sharing = true;
    state.pool_size = 2;
    state.busy_count = 2;
    state.pending_request_count = 3;
    state.max_pending_request_count = 4;
    state.queue_timeout_count = 1;
    state.deadline_exceeded_count = 1;
    state.queued_request_count = 5;
    state.avg_queue_wait_ms = 72.0;
    state.max_queue_wait_ms = 140;
    state.batch_metrics = {
        {"formed_batch_count", 4},
        {"timeout_flush_count", 3},
        {"full_flush_count", 1},
    };

    const auto assessment = ResourceOrchestrator::EvaluateCapability(state);
    if (!Expect(assessment["backpressure_level"] == "hard", "orchestrator should raise hard backpressure")) {
        return 1;
    }
    if (!Expect(assessment["recommended_pool_size"] == 3, "orchestrator should recommend scaling pool")) {
        return 1;
    }
    if (!Expect(assessment["recommended_max_batch_size"] == 3, "orchestrator should recommend shrinking batch size")) {
        return 1;
    }
    if (!Expect(assessment["resource_sharing_allowed"] == true, "orchestrator should expose resource sharing flag")) {
        return 1;
    }

    const auto summary = ResourceOrchestrator::BuildSummary({assessment});
    if (!Expect(summary["overall_state"] == "degraded", "summary should surface degraded state")) {
        return 1;
    }
    if (!Expect(summary["hotspot_capability"] == "face_detect", "summary should expose hotspot capability")) {
        return 1;
    }
    return 0;
}
