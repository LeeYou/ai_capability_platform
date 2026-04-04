#include "request_lease.h"

RequestLease::RequestLease(
    std::shared_ptr<InstancePool> pool_value,
    InstancePoolItem item_value,
    std::shared_ptr<InFlightRequestTracker> request_tracker,
    const std::string& capability_name,
    const std::string& request_id,
    int requested_deadline_ms)
    : pool(std::move(pool_value)),
      item(std::move(item_value)),
      requestTracker(std::move(request_tracker)),
      requestId(request_id) {
    if (requestTracker) {
        requestTracker->Register(requestId, capability_name, item.instance_id, item.slot_index, requested_deadline_ms);
    }
}

RequestLease::~RequestLease() {
    if (pool) {
        pool->Release(item.slot_index);
    }
    if (!requestTracker || requestId.empty()) {
        return;
    }
    if (completed) {
        requestTracker->MarkCompleted(requestId);
        return;
    }
    requestTracker->MarkFailed(requestId, failureReason.empty() ? "request_aborted" : failureReason);
}

const InstancePoolItem& RequestLease::Item() const {
    return item;
}

const std::string& RequestLease::RequestId() const {
    return requestId;
}

void RequestLease::MarkExecuting(const std::string& device) {
    if (requestTracker) {
        requestTracker->MarkExecuting(requestId, device);
    }
}

void RequestLease::MarkSlaStatus(const std::string& sla_status) {
    if (requestTracker) {
        requestTracker->MarkSlaStatus(requestId, sla_status);
    }
}

void RequestLease::MarkCompleted() {
    completed = true;
    failed = false;
    failureReason.clear();
}

void RequestLease::MarkFailed(const std::string& error_message) {
    failed = true;
    completed = false;
    failureReason = error_message;
}
