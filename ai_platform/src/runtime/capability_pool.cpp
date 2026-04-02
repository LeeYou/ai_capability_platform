#include "capability_pool.h"

#include <cstring>

namespace ai_platform {

CapabilityPool::CapabilityPool() = default;

CapabilityPool::~CapabilityPool() {
    std::lock_guard<std::mutex> lock(mutex_);
    destroy_owned_instances();
}

void CapabilityPool::bind(const PluginRuntimeEntry& plugin, std::size_t instance_count) {
    std::lock_guard<std::mutex> lock(mutex_);
    destroy_owned_instances();
    instances_.clear();
    draining_ = false;

    const std::size_t target_count = instance_count == 0 ? 1U : instance_count;
    instances_.reserve(target_count);

    InstanceSlot primary_slot;
    if (!initialize_instance(primary_slot, plugin, false)) {
        instances_.clear();
        return;
    }
    instances_.push_back(primary_slot);

    for (std::size_t i = 1; i < target_count; ++i) {
        InstanceSlot extra_slot;
        if (!initialize_instance(extra_slot, plugin, true)) {
            break;
        }
        instances_.push_back(extra_slot);
    }
}

CapabilityPoolLease CapabilityPool::acquire() {
    std::lock_guard<std::mutex> lock(mutex_);
    if (draining_) {
        return {};
    }

    for (std::size_t i = 0; i < instances_.size(); ++i) {
        auto& slot = instances_[i];
        if (slot.entry.plugin_handle == nullptr || slot.busy) {
            continue;
        }
        slot.busy = true;
        return {&slot.entry, i};
    }
    return {};
}

void CapabilityPool::release(const CapabilityPoolLease& lease) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (lease.index >= instances_.size()) {
        return;
    }
    instances_[lease.index].busy = false;
}

void CapabilityPool::begin_drain() {
    std::lock_guard<std::mutex> lock(mutex_);
    draining_ = true;
}

void CapabilityPool::end_drain() {
    std::lock_guard<std::mutex> lock(mutex_);
    draining_ = false;
}

bool CapabilityPool::can_drain() const {
    std::lock_guard<std::mutex> lock(mutex_);
    for (const auto& slot : instances_) {
        if (slot.busy) {
            return false;
        }
    }
    return true;
}

bool CapabilityPool::drain() {
    std::lock_guard<std::mutex> lock(mutex_);
    draining_ = true;
    for (const auto& slot : instances_) {
        if (slot.busy) {
            return false;
        }
    }

    destroy_owned_instances();
    instances_.clear();
    draining_ = false;
    return true;
}

std::size_t CapabilityPool::size() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return instances_.size();
}

std::size_t CapabilityPool::busy_count() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::size_t count = 0;
    for (const auto& slot : instances_) {
        if (slot.busy) {
            ++count;
        }
    }
    return count;
}

bool CapabilityPool::is_draining() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return draining_;
}

bool CapabilityPool::is_ready() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return !instances_.empty() && !draining_;
}

bool CapabilityPool::initialize_instance(InstanceSlot& slot, const PluginRuntimeEntry& plugin_template, bool owned_handle) {
    slot.entry = plugin_template;
    slot.owned_handle = owned_handle;
    slot.busy = false;

    if (!owned_handle) {
        return slot.entry.plugin_handle != nullptr;
    }

    slot.entry.plugin_handle = nullptr;

    if (slot.entry.init == nullptr) {
        return false;
    }

    AiPluginInitParams init_params{};
    init_params.model_dir = slot.entry.model_dir.c_str();
    init_params.device = slot.entry.device;
    init_params.device_id = 0;
    init_params.max_batch_size = slot.entry.max_batch_size;
    init_params.extra_config = "{}";
    init_params.log_level = 3;

    if (slot.entry.init(&init_params, &slot.entry.plugin_handle) != 0 || slot.entry.plugin_handle == nullptr) {
        return false;
    }

    if (slot.entry.get_info != nullptr) {
        std::memset(&slot.entry.plugin_info, 0, sizeof(slot.entry.plugin_info));
        slot.entry.get_info(slot.entry.plugin_handle, &slot.entry.plugin_info);
    }

    return true;
}

void CapabilityPool::destroy_owned_instances() {
    for (auto& slot : instances_) {
        if (!slot.owned_handle || slot.entry.plugin_handle == nullptr) {
            continue;
        }
        if (slot.entry.destroy != nullptr) {
            slot.entry.destroy(slot.entry.plugin_handle);
        }
        slot.entry.plugin_handle = nullptr;
    }
}

}
