#include "request_batcher.h"

#include <algorithm>

namespace {

constexpr int kMinBatchWaitTimeoutMs = 1;

}

BatchDispatchAssignment RequestBatcher::Submit(
    const std::string& capability_name,
    const std::string& request_id,
    int max_batch_size,
    int batch_wait_timeout_ms) {
    std::unique_lock<std::mutex> guard(mutex);
    auto& queue = queues[capability_name];
    auto request = std::make_shared<PendingRequest>();
    request->request_id = request_id;
    request->enqueued_at = std::chrono::steady_clock::now();
    queue.pending.push_back(request);

    const int effective_max_batch_size = std::max(1, max_batch_size);
    const int effective_batch_wait_timeout_ms = std::max(kMinBatchWaitTimeoutMs, batch_wait_timeout_ms);

    while (!request->released) {
        const auto now = std::chrono::steady_clock::now();
        if (ReleaseBatchUnlocked(
                capability_name,
                &queue,
                effective_max_batch_size,
                effective_batch_wait_timeout_ms,
                nextBatchNumber,
                now)) {
            nextBatchNumber += 1;
            queue.condition.notify_all();
            continue;
        }

        const auto wait_deadline = queue.pending.front()->enqueued_at + std::chrono::milliseconds(effective_batch_wait_timeout_ms);
        queue.condition.wait_until(guard, wait_deadline);
    }

    return request->assignment;
}

std::optional<nlohmann::json> RequestBatcher::GetCapabilityMetrics(const std::string& capability_name) const {
    std::lock_guard<std::mutex> guard(mutex);
    const auto it = queues.find(capability_name);
    if (it == queues.end()) {
        return std::nullopt;
    }

    const auto& queue = it->second;
    return nlohmann::json{
        {"pending_batch_request_count", static_cast<int>(queue.pending.size())},
        {"formed_batch_count", queue.formed_batch_count},
        {"timeout_flush_count", queue.timeout_flush_count},
        {"full_flush_count", queue.full_flush_count},
        {"total_batched_request_count", queue.total_batched_request_count},
        {"avg_batch_size", queue.formed_batch_count > 0
                               ? static_cast<double>(queue.total_batched_request_count) / static_cast<double>(queue.formed_batch_count)
                               : 0.0},
        {"max_batch_size_observed", queue.max_batch_size_observed},
        {"last_batch_size", queue.last_batch_size},
        {"last_batch_wait_ms", queue.last_batch_wait_ms},
        {"max_batch_wait_ms", queue.max_batch_wait_ms},
        {"last_batch_id", queue.last_batch_id.empty() ? nlohmann::json(nullptr) : nlohmann::json(queue.last_batch_id)},
    };
}

bool RequestBatcher::ReleaseBatchUnlocked(
    const std::string& capability_name,
    CapabilityQueue* queue,
    int max_batch_size,
    int batch_wait_timeout_ms,
    std::uint64_t batch_number,
    std::chrono::steady_clock::time_point now) {
    if (queue == nullptr || queue->pending.empty()) {
        return false;
    }

    const bool size_triggered = static_cast<int>(queue->pending.size()) >= max_batch_size;
    const bool timeout_triggered =
        now >= queue->pending.front()->enqueued_at + std::chrono::milliseconds(batch_wait_timeout_ms);
    if (!size_triggered && !timeout_triggered) {
        return false;
    }

    const auto release_count = std::min<std::size_t>(static_cast<std::size_t>(max_batch_size), queue->pending.size());
    std::vector<std::shared_ptr<PendingRequest>> released_requests;
    released_requests.reserve(release_count);
    for (std::size_t index = 0; index < release_count; ++index) {
        released_requests.push_back(queue->pending.front());
        queue->pending.pop_front();
    }

    const auto batch_id = BuildBatchId(capability_name, batch_number);
    std::vector<std::string> request_ids;
    request_ids.reserve(released_requests.size());
    for (const auto& request : released_requests) {
        request_ids.push_back(request->request_id);
    }

    int batch_wait_ms = 0;
    for (std::size_t index = 0; index < released_requests.size(); ++index) {
        auto& request = released_requests[index];
        request->released = true;
        request->assignment.batch_id = batch_id;
        request->assignment.batch_size = released_requests.size();
        request->assignment.batch_index = index;
        request->assignment.batch_wait_ms = static_cast<int>(
            std::chrono::duration_cast<std::chrono::milliseconds>(now - request->enqueued_at).count());
        request->assignment.leader = index == 0;
        request->assignment.timeout_triggered = timeout_triggered && !size_triggered;
        request->assignment.request_ids = request_ids;
        batch_wait_ms = std::max(batch_wait_ms, request->assignment.batch_wait_ms);
    }

    queue->formed_batch_count += 1;
    queue->total_batched_request_count += static_cast<int>(released_requests.size());
    queue->max_batch_size_observed = std::max(queue->max_batch_size_observed, static_cast<int>(released_requests.size()));
    queue->last_batch_size = static_cast<int>(released_requests.size());
    queue->last_batch_wait_ms = batch_wait_ms;
    queue->max_batch_wait_ms = std::max(queue->max_batch_wait_ms, batch_wait_ms);
    queue->last_batch_id = batch_id;
    if (size_triggered) {
        queue->full_flush_count += 1;
    } else {
        queue->timeout_flush_count += 1;
    }
    return true;
}

std::string RequestBatcher::BuildBatchId(const std::string& capability_name, std::uint64_t batch_number) {
    return capability_name + "-batch-" + std::to_string(batch_number);
}
