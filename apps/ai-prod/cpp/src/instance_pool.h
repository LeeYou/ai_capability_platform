#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H

#include <cstddef>
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

class InstancePool {
public:
    InstancePool() = default;

    void Reset(const std::string& capability_name, int pool_size, bool gpu_available);
    std::optional<InstancePoolItem> Acquire();
    bool Release(std::size_t slot_index);
    int GetBusyCount() const;
    int GetTotalSize() const;
    std::vector<InstancePoolItem> Snapshot() const;

private:
    mutable std::mutex mutex;
    std::vector<InstancePoolItem> items;
};

#endif
