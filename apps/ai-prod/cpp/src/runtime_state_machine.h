#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_STATE_MACHINE_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_RUNTIME_STATE_MACHINE_H

#include <mutex>
#include <string>

enum class RuntimeLifecycleState {
    kUninitialized,
    kBootstrapping,
    kReady,
    kDraining,
    kTransitioning,
    kError,
};

class RuntimeStateMachine {
public:
    RuntimeStateMachine() = default;

    RuntimeLifecycleState GetState() const;
    std::string GetStateName() const;
    std::string GetLastError() const;
    bool TransitionTo(RuntimeLifecycleState next_state, std::string* error_message);
    void MarkError(const std::string& error_message);

private:
    static bool IsTransitionAllowed(RuntimeLifecycleState current_state, RuntimeLifecycleState next_state);
    static std::string StateName(RuntimeLifecycleState state);

    mutable std::mutex mutex;
    RuntimeLifecycleState state = RuntimeLifecycleState::kUninitialized;
    std::string lastError;
};

#endif
