#ifndef AI_PLATFORM_RELOAD_CONTROLLER_H
#define AI_PLATFORM_RELOAD_CONTROLLER_H

#include "ai_runtime.h"
#include "pool_manager.h"
#include "plugin_manager.h"

namespace ai_platform {

class ReloadController {
public:
    ReloadController(PluginManager& plugin_manager, PoolManager& pool_manager);

    RuntimeReloadResult reload_capability(const std::string& capability_id, RuntimeReloadType reload_type, const std::string& target_model_dir) const;
    RuntimeReloadResult reload_all_capabilities(RuntimeReloadType reload_type, const std::string& target_model_dir) const;
    RuntimeReloadResult rollback_capability(const std::string& capability_id) const;
    RuntimeReloadResult rollback_all_capabilities(const std::vector<CapabilityInfo>& capabilities) const;

private:
    RuntimeReloadResult build_reload_failure_result(const std::string& capability_id,
                                                    RuntimeReloadType reload_type,
                                                    const std::string& target_model_dir,
                                                    const std::string& current_stage,
                                                    const std::string& message) const;

    PluginManager& plugin_manager_;
    PoolManager& pool_manager_;
};

}

#endif
