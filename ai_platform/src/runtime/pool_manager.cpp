#include "pool_manager.h"

namespace ai_platform {

void PoolManager::rebuild(const std::unordered_map<std::string, PluginRuntimeEntry>& plugins) {
    pools_.clear();
    for (const auto& pair : plugins) {
        auto [it, inserted] = pools_.try_emplace(pair.first);
        const std::size_t instance_count = pair.second.instance_count > 1 ? static_cast<std::size_t>(pair.second.instance_count) : 1U;
        it->second.bind(pair.second, instance_count);
    }
}

bool PoolManager::begin_drain(const std::string& capability_id) {
    auto* pool = get_pool(capability_id);
    if (pool == nullptr) {
        return false;
    }
    pool->begin_drain();
    return true;
}

bool PoolManager::begin_drain_all() {
    if (pools_.empty()) {
        return false;
    }
    for (auto& pair : pools_) {
        pair.second.begin_drain();
    }
    return true;
}

bool PoolManager::end_drain(const std::string& capability_id) {
    auto* pool = get_pool(capability_id);
    if (pool == nullptr) {
        return false;
    }
    pool->end_drain();
    return true;
}

bool PoolManager::end_drain_all() {
    if (pools_.empty()) {
        return false;
    }
    for (auto& pair : pools_) {
        pair.second.end_drain();
    }
    return true;
}

bool PoolManager::can_drain(const std::string& capability_id) const {
    const auto* pool = get_pool(capability_id);
    if (pool == nullptr) {
        return false;
    }
    return pool->can_drain();
}

bool PoolManager::can_drain_all() const {
    if (pools_.empty()) {
        return false;
    }
    for (const auto& pair : pools_) {
        if (!pair.second.can_drain()) {
            return false;
        }
    }
    return true;
}

CapabilityPool* PoolManager::get_pool(const std::string& capability_id) {
    const auto it = pools_.find(capability_id);
    if (it == pools_.end()) {
        return nullptr;
    }
    return &it->second;
}

const CapabilityPool* PoolManager::get_pool(const std::string& capability_id) const {
    const auto it = pools_.find(capability_id);
    if (it == pools_.end()) {
        return nullptr;
    }
    return &it->second;
}

}
