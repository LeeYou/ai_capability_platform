#ifndef AI_PLATFORM_POOL_MANAGER_H
#define AI_PLATFORM_POOL_MANAGER_H

#include "capability_pool.h"

#include <string>
#include <unordered_map>

namespace ai_platform {

class PoolManager {
public:
    void rebuild(const std::unordered_map<std::string, PluginRuntimeEntry>& plugins);
    bool begin_drain(const std::string& capability_id);
    bool begin_drain_all();
    bool end_drain(const std::string& capability_id);
    bool end_drain_all();
    bool can_drain(const std::string& capability_id) const;
    bool can_drain_all() const;
    CapabilityPool* get_pool(const std::string& capability_id);
    const CapabilityPool* get_pool(const std::string& capability_id) const;

private:
    std::unordered_map<std::string, CapabilityPool> pools_;
};

}

#endif
