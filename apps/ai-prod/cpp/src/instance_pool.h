#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_INSTANCE_POOL_H

#include <chrono>
#include <cstddef>
#include <condition_variable>
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
    void BeginDrain();
    void EndDrain();
    bool WaitForIdle(std::chrono::milliseconds timeout);
    bool IsDraining() const;
    int GetBusyCount() const;
    int GetTotalSize() const;
    std::vector<InstancePoolItem> Snapshot() const;

private:
    bool IsIdleUnlocked() const;

    mutable std::condition_variable condition;
    mutable std::mutex mutex;
    std::vector<InstancePoolItem> items;
    bool draining = false;
};

#endif
