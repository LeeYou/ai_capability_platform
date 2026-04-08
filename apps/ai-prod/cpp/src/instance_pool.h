#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H

#include <chrono>
#include <cstddef>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

struct InstancePoolItem {
    std::size_t slot_index = 0;
    std::string instance_id;
    std::string preferred_device;
    bool in_use = false;
};

enum class InstanceAcquireStatus {
    kAcquired,
    kDraining,
    kQueueRejected,
    kDeadlineExceeded,
    kTimedOut,
};

struct InstanceAcquireResult {
    InstanceAcquireStatus status = InstanceAcquireStatus::kTimedOut;
    std::optional<InstancePoolItem> item;
    int queue_wait_ms = 0;
    bool deadline_exceeded = false;
};

class InstancePool {
public:
    InstancePool() = default;

    void Reset(const std::string& capability_name, int pool_size, bool gpu_available);
    std::optional<InstancePoolItem> Acquire();
    InstanceAcquireResult AcquireWithWait(
        std::chrono::milliseconds timeout,
        int max_pending_requests,
        std::optional<std::chrono::milliseconds> request_deadline = std::nullopt);
    bool Release(std::size_t slot_index);
    void BeginDrain();
    void EndDrain();
    bool WaitForIdle(std::chrono::milliseconds timeout);
    bool IsDraining() const;
    int GetBusyCount() const;
    int GetBusyRejectCount() const;
    int GetPendingCount() const;
    int GetMaxPendingCount() const;
    int GetQueueTimeoutCount() const;
    int GetDeadlineExceededCount() const;
    int GetQueuedRequestCount() const;
    void RecordDeadlineExceeded();
    double GetAverageQueueWaitMs() const;
    std::int64_t GetTotalQueueWaitMs() const;
    int GetMaxQueueWaitMs() const;
    int GetTotalSize() const;
    std::vector<InstancePoolItem> Snapshot() const;

private:
    bool HasAvailableSlotUnlocked() const;
    std::optional<InstancePoolItem> TryAcquireUnlocked();
    bool IsIdleUnlocked() const;

    mutable std::condition_variable condition;
    mutable std::mutex mutex;
    std::vector<InstancePoolItem> items;
    bool draining = false;
    int busyRejectCount = 0;
    int pendingCount = 0;
    int maxPendingCount = 0;
    int queueTimeoutCount = 0;
    int deadlineExceededCount = 0;
    int queuedRequestCount = 0;
    long long totalQueueWaitMs = 0;
    int maxQueueWaitMs = 0;
};

#endif
