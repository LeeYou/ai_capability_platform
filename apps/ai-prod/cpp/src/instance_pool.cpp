#include "instance_pool.h"

#include <algorithm>

void InstancePool::Reset(const std::string& capability_name, int pool_size, bool gpu_available) {
    std::lock_guard<std::mutex> guard(mutex);
    draining = false;
    busyRejectCount = 0;
    pendingCount = 0;
    maxPendingCount = 0;
    queueTimeoutCount = 0;
    queuedRequestCount = 0;
    totalQueueWaitMs = 0;
    maxQueueWaitMs = 0;
    items.clear();
    items.reserve(static_cast<std::size_t>(std::max(pool_size, 0)));
    for (int index = 0; index < pool_size; ++index) {
        items.push_back(InstancePoolItem{
            static_cast<std::size_t>(index),
            capability_name + "-" + std::to_string(index + 1),
            gpu_available ? "gpu" : "cpu",
            false,
        });
    }
    condition.notify_all();
}

std::optional<InstancePoolItem> InstancePool::Acquire() {
    std::lock_guard<std::mutex> guard(mutex);
    if (draining) {
        return std::nullopt;
    }
    const auto item = TryAcquireUnlocked();
    if (item.has_value()) {
        return item;
    }
    busyRejectCount += 1;
    return std::nullopt;
}

InstanceAcquireResult InstancePool::AcquireWithWait(std::chrono::milliseconds timeout, int max_pending_requests) {
    std::unique_lock<std::mutex> guard(mutex);
    if (draining) {
        return {InstanceAcquireStatus::kDraining, std::nullopt, 0};
    }
    if (const auto item = TryAcquireUnlocked(); item.has_value()) {
        return {InstanceAcquireStatus::kAcquired, item, 0};
    }
    if (max_pending_requests > 0 && pendingCount >= max_pending_requests) {
        busyRejectCount += 1;
        return {InstanceAcquireStatus::kQueueRejected, std::nullopt, 0};
    }

    const auto queued_at = std::chrono::steady_clock::now();
    const auto deadline = queued_at + timeout;
    pendingCount += 1;
    maxPendingCount = std::max(maxPendingCount, pendingCount);

    const auto cleanup_pending = [this]() {
        pendingCount = std::max(0, pendingCount - 1);
    };
    while (true) {
        const auto now = std::chrono::steady_clock::now();
        const auto remaining = deadline > now
                                   ? std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now)
                                   : std::chrono::milliseconds(0);
        if (condition.wait_for(guard, remaining, [&]() {
                return draining || HasAvailableSlotUnlocked();
            })) {
            if (draining) {
                cleanup_pending();
                return {InstanceAcquireStatus::kDraining, std::nullopt, 0};
            }
            auto item = TryAcquireUnlocked();
            if (item.has_value()) {
                cleanup_pending();
                const int queue_wait_ms = static_cast<int>(
                    std::chrono::duration_cast<std::chrono::milliseconds>(
                        std::chrono::steady_clock::now() - queued_at)
                        .count());
                queuedRequestCount += 1;
                totalQueueWaitMs += queue_wait_ms;
                maxQueueWaitMs = std::max(maxQueueWaitMs, queue_wait_ms);
                return {InstanceAcquireStatus::kAcquired, item, queue_wait_ms};
            }
            continue;
        }

        cleanup_pending();
        busyRejectCount += 1;
        queueTimeoutCount += 1;
        return {InstanceAcquireStatus::kTimedOut, std::nullopt, static_cast<int>(
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - queued_at)
                .count())};
    }
}

bool InstancePool::Release(std::size_t slot_index) {
    std::lock_guard<std::mutex> guard(mutex);
    if (slot_index >= items.size()) {
        return false;
    }
    if (!items[slot_index].in_use) {
        return false;
    }
    items[slot_index].in_use = false;
    condition.notify_all();
    return true;
}

void InstancePool::BeginDrain() {
    std::lock_guard<std::mutex> guard(mutex);
    draining = true;
    if (IsIdleUnlocked()) {
        condition.notify_all();
    }
}

void InstancePool::EndDrain() {
    std::lock_guard<std::mutex> guard(mutex);
    draining = false;
    condition.notify_all();
}

bool InstancePool::WaitForIdle(std::chrono::milliseconds timeout) {
    std::unique_lock<std::mutex> guard(mutex);
    return condition.wait_for(guard, timeout, [&]() { return IsIdleUnlocked(); });
}

bool InstancePool::IsDraining() const {
    std::lock_guard<std::mutex> guard(mutex);
    return draining;
}

int InstancePool::GetBusyCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(std::count_if(
        items.begin(),
        items.end(),
        [](const InstancePoolItem& item) { return item.in_use; }));
}

int InstancePool::GetBusyRejectCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return busyRejectCount;
}

int InstancePool::GetPendingCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return pendingCount;
}

int InstancePool::GetMaxPendingCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return maxPendingCount;
}

int InstancePool::GetQueueTimeoutCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return queueTimeoutCount;
}

int InstancePool::GetQueuedRequestCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return queuedRequestCount;
}

double InstancePool::GetAverageQueueWaitMs() const {
    std::lock_guard<std::mutex> guard(mutex);
    if (queuedRequestCount <= 0) {
        return 0.0;
    }
    return static_cast<double>(totalQueueWaitMs) / static_cast<double>(queuedRequestCount);
}

int InstancePool::GetMaxQueueWaitMs() const {
    std::lock_guard<std::mutex> guard(mutex);
    return maxQueueWaitMs;
}

int InstancePool::GetTotalSize() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(items.size());
}

std::vector<InstancePoolItem> InstancePool::Snapshot() const {
    std::lock_guard<std::mutex> guard(mutex);
    return items;
}

std::optional<InstancePoolItem> InstancePool::TryAcquireUnlocked() {
    for (auto& item : items) {
        if (!item.in_use) {
            item.in_use = true;
            return item;
        }
    }
    return std::nullopt;
}

bool InstancePool::HasAvailableSlotUnlocked() const {
    return std::any_of(items.begin(), items.end(), [](const InstancePoolItem& item) { return !item.in_use; });
}

bool InstancePool::IsIdleUnlocked() const {
    return std::none_of(items.begin(), items.end(), [](const InstancePoolItem& item) { return item.in_use; });
}
