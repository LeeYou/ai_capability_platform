#include "request_tracker.h"

#include <chrono>
#include <iostream>
#include <thread>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

}

int main() {
    InFlightRequestTracker tracker;
    tracker.Register("req-1", "face_detect", "face_detect-1", 0);
    if (!Expect(tracker.GetActiveCount() == 1, "tracker should count registered request")) {
        return 1;
    }
    if (!Expect(tracker.MarkExecuting("req-1", "gpu"), "tracker should mark request executing")) {
        return 1;
    }
    const auto snapshot = tracker.Snapshot();
    if (!Expect(snapshot.size() == 1, "tracker snapshot should contain active request")) {
        return 1;
    }
    if (!Expect(snapshot[0].device == "gpu", "tracker snapshot should record device")) {
        return 1;
    }
    if (!Expect(snapshot[0].status == "executing", "tracker snapshot should record status")) {
        return 1;
    }
    if (!Expect(snapshot[0].ElapsedMs(std::chrono::steady_clock::now()) >= 0, "tracker snapshot should calculate elapsed time")) {
        return 1;
    }
    if (!Expect(tracker.MarkCompleted("req-1"), "tracker should complete request")) {
        return 1;
    }
    if (!Expect(tracker.GetActiveCount() == 0, "tracker should clear completed request")) {
        return 1;
    }

    tracker.Register("req-2", "ocr", "ocr-1", 1);
    std::thread worker([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        tracker.MarkFailed("req-2", "mock failed");
    });
    if (!Expect(tracker.WaitForEmpty(std::chrono::milliseconds(500)), "tracker should wait until requests finish")) {
        worker.join();
        return 1;
    }
    worker.join();
    return 0;
}
