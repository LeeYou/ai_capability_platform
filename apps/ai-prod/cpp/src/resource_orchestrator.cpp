#include "resource_orchestrator.h"

#include <algorithm>

namespace {

double ResolveUtilizationRatio(const ResourceOrchestratorCapabilityState& state) {
    if (state.pool_size <= 0) {
        return 0.0;
    }
    return static_cast<double>(state.busy_count) / static_cast<double>(state.pool_size);
}

int ResolveConfiguredMaxPending(const ResourceOrchestratorCapabilityState& state) {
    if (state.entry.max_pending_request_count >= 0) {
        return state.entry.max_pending_request_count;
    }
    return state.max_pending_request_count;
}

const char* ResolveSchedulingMode(
    double utilization_ratio,
    int deadline_exceeded_count,
    int timeout_flush_count,
    int full_flush_count) {
    if (deadline_exceeded_count > 0) {
        return "latency_first";
    }
    if (full_flush_count > timeout_flush_count && utilization_ratio >= 0.6) {
        return "throughput_first";
    }
    return "balanced";
}

}

nlohmann::json ResourceOrchestrator::EvaluateCapability(const ResourceOrchestratorCapabilityState& state) {
    const double utilization_ratio = ResolveUtilizationRatio(state);
    const int configured_max_pending = ResolveConfiguredMaxPending(state);
    const int timeout_flush_count = state.batch_metrics.value("timeout_flush_count", 0);
    const int full_flush_count = state.batch_metrics.value("full_flush_count", 0);
    const int formed_batch_count = state.batch_metrics.value("formed_batch_count", 0);
    const int recommended_pool_size = std::max(
        state.pool_size,
        state.pending_request_count > 0 || utilization_ratio >= 0.85
            ? state.pool_size + 1
            : state.pool_size);
    int recommended_batch_size = std::max(state.entry.min_batch_size, state.entry.max_batch_size);
    if (state.entry.max_batch_size > state.entry.min_batch_size &&
        timeout_flush_count > full_flush_count &&
        formed_batch_count > 0) {
        recommended_batch_size = std::max(state.entry.min_batch_size, state.entry.max_batch_size - 1);
    }
    const bool hard_backpressure =
        state.deadline_exceeded_count > 0 ||
        (configured_max_pending > 0 && state.pending_request_count >= configured_max_pending);
    const bool soft_backpressure =
        !hard_backpressure &&
        (state.queue_timeout_count > 0 || state.pending_request_count > 0 || utilization_ratio >= 0.85);

    nlohmann::json reasons = nlohmann::json::array();
    if (utilization_ratio >= 0.85) {
        reasons.push_back("实例池利用率已接近饱和");
    }
    if (state.pending_request_count > 0) {
        reasons.push_back("存在待处理请求，需要关注排队压力");
    }
    if (state.deadline_exceeded_count > 0) {
        reasons.push_back("已出现 SLA deadline 违约");
    }
    if (state.queue_timeout_count > 0) {
        reasons.push_back("已出现排队超时");
    }
    if (timeout_flush_count > full_flush_count && formed_batch_count > 0) {
        reasons.push_back("批次更多由超时触发，可适当下调批次规模");
    }
    if (full_flush_count > 0 && timeout_flush_count == 0) {
        reasons.push_back("批次稳定按满批触发，可继续采用吞吐优先调度");
    }
    if (reasons.empty()) {
        reasons.push_back("当前 capability 运行态平稳");
    }

    return {
        {"capability_name", state.entry.capability_name},
        {"scheduling_mode", ResolveSchedulingMode(utilization_ratio, state.deadline_exceeded_count, timeout_flush_count, full_flush_count)},
        {"backpressure_level", hard_backpressure ? "hard" : (soft_backpressure ? "soft" : "none")},
        {"recommended_pool_size", recommended_pool_size},
        {"recommended_max_batch_size", recommended_batch_size},
        {"recommended_min_batch_size", state.entry.min_batch_size},
        {"recommended_max_concurrent_requests", state.entry.max_concurrent_requests > 0
                                                    ? std::min(recommended_pool_size, state.entry.max_concurrent_requests)
                                                    : recommended_pool_size},
        {"resource_sharing_allowed", state.entry.allow_resource_sharing},
        {"supports_concurrent_infer", state.entry.supports_concurrent_infer},
        {"utilization_ratio", utilization_ratio},
        {"priority", state.entry.capability_priority},
        {"risk_score", std::min(
             100,
             static_cast<int>(utilization_ratio * 45.0) +
                 std::min(20, state.pending_request_count * 5) +
                 std::min(20, state.deadline_exceeded_count * 10) +
                 std::min(15, state.queue_timeout_count * 5))},
        {"estimated_avg_infer_time_ms", state.entry.estimated_avg_infer_time_ms},
        {"p95_infer_time_ms", state.entry.p95_infer_time_ms},
        {"infer_timeout_ms", state.entry.infer_timeout_ms},
        {"reasons", reasons},
    };
}

nlohmann::json ResourceOrchestrator::BuildSummary(const std::vector<nlohmann::json>& capability_assessments) {
    int hard_backpressure_count = 0;
    int soft_backpressure_count = 0;
    int max_risk_score = 0;
    std::string hotspot_capability;
    nlohmann::json hotspot_capabilities = nlohmann::json::array();
    for (const auto& assessment : capability_assessments) {
        const auto level = assessment.value("backpressure_level", "none");
        if (level == "hard") {
            hard_backpressure_count += 1;
        } else if (level == "soft") {
            soft_backpressure_count += 1;
        }
        const int risk_score = assessment.value("risk_score", 0);
        if (risk_score >= max_risk_score) {
            max_risk_score = risk_score;
            hotspot_capability = assessment.value("capability_name", "");
        }
        if (risk_score >= 50 || level != "none") {
            hotspot_capabilities.push_back(assessment.value("capability_name", ""));
        }
    }

    return {
        {"capability_count", capability_assessments.size()},
        {"hard_backpressure_count", hard_backpressure_count},
        {"soft_backpressure_count", soft_backpressure_count},
        {"hotspot_capability", hotspot_capability.empty() ? nlohmann::json(nullptr) : nlohmann::json(hotspot_capability)},
        {"hotspot_capabilities", hotspot_capabilities},
        {"overall_state", hard_backpressure_count > 0 ? "degraded" : (soft_backpressure_count > 0 ? "attention" : "stable")},
    };
}
