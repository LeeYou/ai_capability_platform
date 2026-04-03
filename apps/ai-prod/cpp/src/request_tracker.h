#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_TRACKER_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_TRACKER_H

#include <chrono>
#include <condition_variable>
#include <cstddef>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

struct InFlightRequestInfo {
    std::string request_id;
    std::string capability_name;
    std::string instance_id;
    std::string device;
    std::size_t slot_index = 0;
    std::string status = "registered";
    std::optional<std::string> error_message;
    std::chrono::steady_clock::time_point started_at = std::chrono::steady_clock::now();
};

class InFlightRequestTracker {
public:
    void Register(
        const std::string& request_id,
        const std::string& capability_name,
        const std::string& instance_id,
        std::size_t slot_index);
    bool MarkExecuting(const std::string& request_id, const std::string& device);
    bool MarkCompleted(const std::string& request_id);
    bool MarkFailed(const std::string& request_id, const std::string& error_message);
    int GetActiveCount() const;
    std::vector<InFlightRequestInfo> Snapshot() const;
    bool WaitForEmpty(std::chrono::milliseconds timeout) const;

private:
    mutable std::condition_variable condition;
    mutable std::mutex mutex;
    std::map<std::string, InFlightRequestInfo> requests;
};

#endif
