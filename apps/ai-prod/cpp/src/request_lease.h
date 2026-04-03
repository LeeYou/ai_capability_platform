#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_LEASE_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_REQUEST_LEASE_H

#include "instance_pool.h"
#include "request_tracker.h"

#include <memory>
#include <string>

class RequestLease {
public:
    RequestLease(
        std::shared_ptr<InstancePool> pool,
        InstancePoolItem item,
        std::shared_ptr<InFlightRequestTracker> request_tracker,
        const std::string& capability_name,
        const std::string& request_id);
    ~RequestLease();

    RequestLease(const RequestLease&) = delete;
    RequestLease& operator=(const RequestLease&) = delete;

    const InstancePoolItem& Item() const;
    const std::string& RequestId() const;
    void MarkExecuting(const std::string& device);
    void MarkCompleted();
    void MarkFailed(const std::string& error_message);

private:
    std::shared_ptr<InstancePool> pool;
    InstancePoolItem item;
    std::shared_ptr<InFlightRequestTracker> requestTracker;
    std::string requestId;
    bool completed = false;
    bool failed = false;
    std::string failureReason;
};

#endif
