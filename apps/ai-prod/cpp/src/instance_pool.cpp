#include "instance_pool.h"

#include <algorithm>

void InstancePool::Reset(const std::string& capability_name, int pool_size, bool gpu_available) {
    std::lock_guard<std::mutex> guard(mutex);
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
}

std::optional<InstancePoolItem> InstancePool::Acquire() {
    std::lock_guard<std::mutex> guard(mutex);
    for (auto& item : items) {
        if (!item.in_use) {
            item.in_use = true;
            return item;
        }
    }
    return std::nullopt;
}

bool InstancePool::Release(std::size_t slot_index) {
    std::lock_guard<std::mutex> guard(mutex);
    if (slot_index >= items.size()) {
        return false;
    }
    items[slot_index].in_use = false;
    return true;
}

int InstancePool::GetBusyCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(std::count_if(
        items.begin(),
        items.end(),
        [](const InstancePoolItem& item) { return item.in_use; }));
}

int InstancePool::GetTotalSize() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(items.size());
}

std::vector<InstancePoolItem> InstancePool::Snapshot() const {
    std::lock_guard<std::mutex> guard(mutex);
    return items;
}
