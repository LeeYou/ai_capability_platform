#ifndef AI_PLATFORM_CAPABILITY_POOL_H
#define AI_PLATFORM_CAPABILITY_POOL_H

#include "plugin_manager.h"

#include <cstddef>
#include <vector>
#include <mutex>

namespace ai_platform {

struct CapabilityPoolLease {
    PluginRuntimeEntry* plugin = nullptr;
    std::size_t index = 0;
};

class CapabilityPool {
public:
    CapabilityPool();
    ~CapabilityPool();

    CapabilityPool(const CapabilityPool&) = delete;
    CapabilityPool& operator=(const CapabilityPool&) = delete;

    void bind(const PluginRuntimeEntry& plugin, std::size_t instance_count);
    CapabilityPoolLease acquire();
    void release(const CapabilityPoolLease& lease);
    void begin_drain();
    void end_drain();
    bool can_drain() const;
    bool drain();
    std::size_t size() const;
    std::size_t busy_count() const;
    bool is_draining() const;
    bool is_ready() const;

private:
    struct InstanceSlot {
        PluginRuntimeEntry entry{};
        bool owned_handle = false;
        bool busy = false;
    };

    bool initialize_instance(InstanceSlot& slot, const PluginRuntimeEntry& plugin_template, bool owned_handle);
    void destroy_owned_instances();

    std::vector<InstanceSlot> instances_;
    bool draining_ = false;
    mutable std::mutex mutex_;
};

}

#endif
