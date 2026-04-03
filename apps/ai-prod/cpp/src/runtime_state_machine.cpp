#include "runtime_state_machine.h"

namespace {

std::string StateName(RuntimeLifecycleState state) {
    switch (state) {
        case RuntimeLifecycleState::kUninitialized:
            return "uninitialized";
        case RuntimeLifecycleState::kBootstrapping:
            return "bootstrapping";
        case RuntimeLifecycleState::kReady:
            return "ready";
        case RuntimeLifecycleState::kDraining:
            return "draining";
        case RuntimeLifecycleState::kTransitioning:
            return "transitioning";
        case RuntimeLifecycleState::kError:
            return "error";
    }
    return "unknown";
}

std::string BuildTransitionError(RuntimeLifecycleState current_state, RuntimeLifecycleState next_state) {
    return "运行时状态不允许从 " + StateName(current_state) +
           " 切换到 " + StateName(next_state) + "。";
}

}

RuntimeLifecycleState RuntimeStateMachine::GetState() const {
    std::lock_guard<std::mutex> guard(mutex);
    return state;
}

std::string RuntimeStateMachine::GetStateName() const {
    std::lock_guard<std::mutex> guard(mutex);
    return StateName(state);
}

std::string RuntimeStateMachine::GetLastError() const {
    std::lock_guard<std::mutex> guard(mutex);
    return lastError;
}

bool RuntimeStateMachine::TransitionTo(RuntimeLifecycleState next_state, std::string* error_message) {
    std::lock_guard<std::mutex> guard(mutex);
    if (!IsTransitionAllowed(state, next_state)) {
        if (error_message != nullptr) {
            *error_message = BuildTransitionError(state, next_state);
        }
        return false;
    }
    state = next_state;
    if (state != RuntimeLifecycleState::kError) {
        lastError.clear();
    }
    return true;
}

void RuntimeStateMachine::MarkError(const std::string& error_message) {
    std::lock_guard<std::mutex> guard(mutex);
    state = RuntimeLifecycleState::kError;
    lastError = error_message;
}

bool RuntimeStateMachine::IsTransitionAllowed(
    RuntimeLifecycleState current_state,
    RuntimeLifecycleState next_state) {
    if (current_state == next_state) {
        return true;
    }
    switch (current_state) {
        case RuntimeLifecycleState::kUninitialized:
            return next_state == RuntimeLifecycleState::kBootstrapping ||
                   next_state == RuntimeLifecycleState::kReady ||
                   next_state == RuntimeLifecycleState::kError;
        case RuntimeLifecycleState::kBootstrapping:
            return next_state == RuntimeLifecycleState::kReady ||
                   next_state == RuntimeLifecycleState::kError;
        case RuntimeLifecycleState::kReady:
            return next_state == RuntimeLifecycleState::kDraining ||
                   next_state == RuntimeLifecycleState::kError;
        case RuntimeLifecycleState::kDraining:
            return next_state == RuntimeLifecycleState::kReady ||
                   next_state == RuntimeLifecycleState::kTransitioning ||
                   next_state == RuntimeLifecycleState::kError;
        case RuntimeLifecycleState::kTransitioning:
            return next_state == RuntimeLifecycleState::kReady ||
                   next_state == RuntimeLifecycleState::kError;
        case RuntimeLifecycleState::kError:
            return next_state == RuntimeLifecycleState::kBootstrapping ||
                   next_state == RuntimeLifecycleState::kReady;
    }
    return false;
}

std::string RuntimeStateMachine::StateName(RuntimeLifecycleState state) {
    return ::StateName(state);
}
