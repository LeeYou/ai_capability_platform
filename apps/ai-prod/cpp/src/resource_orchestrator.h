#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RESOURCE_ORCHESTRATOR_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RESOURCE_ORCHESTRATOR_H

#include "capability_catalog.h"

#include <nlohmann/json.hpp>

#include <vector>

struct ResourceOrchestratorCapabilityState {
    CapabilityCatalogEntry entry;
    int pool_size = 0;
    int busy_count = 0;
    int pending_request_count = 0;
    int max_pending_request_count = 0;
    int queue_timeout_count = 0;
    int deadline_exceeded_count = 0;
    int queued_request_count = 0;
    double avg_queue_wait_ms = 0.0;
    int max_queue_wait_ms = 0;
    nlohmann::json batch_metrics = nlohmann::json::object();
    nlohmann::json execution_metrics = nlohmann::json::object();
};

class ResourceOrchestrator {
public:
    static nlohmann::json EvaluateCapability(const ResourceOrchestratorCapabilityState& state);
    static nlohmann::json BuildSummary(const std::vector<nlohmann::json>& capability_assessments);
};

#endif
