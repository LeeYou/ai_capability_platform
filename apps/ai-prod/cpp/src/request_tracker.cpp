#include "request_tracker.h"

void InFlightRequestTracker::Register(
    const std::string& request_id,
    const std::string& capability_name,
    const std::string& instance_id,
    std::size_t slot_index) {
    std::lock_guard<std::mutex> guard(mutex);
    requests[request_id] = InFlightRequestInfo{
        request_id,
        capability_name,
        instance_id,
        "",
        slot_index,
        "registered",
        std::nullopt,
        std::chrono::steady_clock::now(),
    };
}

bool InFlightRequestTracker::MarkExecuting(const std::string& request_id, const std::string& device) {
    std::lock_guard<std::mutex> guard(mutex);
    const auto it = requests.find(request_id);
    if (it == requests.end()) {
        return false;
    }
    it->second.device = device;
    it->second.status = "executing";
    return true;
}

bool InFlightRequestTracker::MarkCompleted(const std::string& request_id) {
    std::lock_guard<std::mutex> guard(mutex);
    const auto erased = requests.erase(request_id);
    if (erased > 0 && requests.empty()) {
        condition.notify_all();
    }
    return erased > 0;
}

bool InFlightRequestTracker::MarkFailed(const std::string& request_id, const std::string& error_message) {
    std::lock_guard<std::mutex> guard(mutex);
    const auto it = requests.find(request_id);
    if (it == requests.end()) {
        return false;
    }
    it->second.status = "failed";
    it->second.error_message = error_message;
    requests.erase(it);
    if (requests.empty()) {
        condition.notify_all();
    }
    return true;
}

int InFlightRequestTracker::GetActiveCount() const {
    std::lock_guard<std::mutex> guard(mutex);
    return static_cast<int>(requests.size());
}

std::vector<InFlightRequestInfo> InFlightRequestTracker::Snapshot() const {
    std::lock_guard<std::mutex> guard(mutex);
    std::vector<InFlightRequestInfo> snapshot;
    snapshot.reserve(requests.size());
    for (const auto& item : requests) {
        snapshot.push_back(item.second);
    }
    return snapshot;
}

bool InFlightRequestTracker::WaitForEmpty(std::chrono::milliseconds timeout) const {
    std::unique_lock<std::mutex> guard(mutex);
    return condition.wait_for(guard, timeout, [&]() { return requests.empty(); });
}
