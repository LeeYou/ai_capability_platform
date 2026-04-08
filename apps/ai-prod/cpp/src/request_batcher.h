#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_BATCHER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_BATCHER_H

#include <nlohmann/json.hpp>

#include <condition_variable>
#include <chrono>
#include <cstdint>
#include <deque>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

struct BatchDispatchAssignment {
    std::string batch_id;
    std::size_t batch_size = 1;
    std::size_t batch_index = 0;
    int batch_wait_ms = 0;
    bool leader = false;
    bool timeout_triggered = false;
    std::vector<std::string> request_ids;
};

class RequestBatcher {
public:
    BatchDispatchAssignment Submit(
        const std::string& capability_name,
        const std::string& request_id,
        int max_batch_size,
        int batch_wait_timeout_ms);

    std::optional<nlohmann::json> GetCapabilityMetrics(const std::string& capability_name) const;

private:
    struct PendingRequest {
        std::string request_id;
        std::chrono::steady_clock::time_point enqueued_at = std::chrono::steady_clock::now();
        bool released = false;
        BatchDispatchAssignment assignment;
    };

    struct CapabilityQueue {
        std::deque<std::shared_ptr<PendingRequest>> pending;
        mutable std::condition_variable condition;
        int formed_batch_count = 0;
        int timeout_flush_count = 0;
        int full_flush_count = 0;
        int total_batched_request_count = 0;
        int max_batch_size_observed = 0;
        int last_batch_size = 0;
        int last_batch_wait_ms = 0;
        int max_batch_wait_ms = 0;
        std::string last_batch_id;
    };

    static bool ReleaseBatchUnlocked(
        const std::string& capability_name,
        CapabilityQueue* queue,
        int max_batch_size,
        int batch_wait_timeout_ms,
        std::uint64_t batch_number,
        std::chrono::steady_clock::time_point now);

    static std::string BuildBatchId(const std::string& capability_name, std::uint64_t batch_number);

    mutable std::mutex mutex;
    std::unordered_map<std::string, CapabilityQueue> queues;
    std::uint64_t nextBatchNumber = 1;
};

#endif
