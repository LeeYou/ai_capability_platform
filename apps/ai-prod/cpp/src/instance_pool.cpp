#include "instance_pool.h"

#include <algorithm>

void InstancePool::Reset(const std::string& capability_name, int pool_size, bool gpu_available) {
    std::lock_guard<std::mutex> guard(mutex);
    draining = false;
    busyRejectCount = 0;
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
    for (auto& item : items) {
        if (!item.in_use) {
            item.in_use = true;
            return item;
        }
    }
    busyRejectCount += 1;
    return std::nullopt;
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
    if (IsIdleUnlocked()) {
        condition.notify_all();
    }
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

int InstancePool::GetTotalSize() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(items.size());
}

std::vector<InstancePoolItem> InstancePool::Snapshot() const {
    std::lock_guard<std::mutex> guard(mutex);
    return items;
}

bool InstancePool::IsIdleUnlocked() const {
    return std::none_of(items.begin(), items.end(), [](const InstancePoolItem& item) { return item.in_use; });
}
