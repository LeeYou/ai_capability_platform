#include "request_batcher.h"

#include <chrono>
#include <future>
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
    RequestBatcher batcher;

    auto first = std::async(std::launch::async, [&]() {
        return batcher.Submit("face_detect", "req-1", 3, 40);
    });
    auto second = std::async(std::launch::async, [&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        return batcher.Submit("face_detect", "req-2", 3, 40);
    });
    auto third = std::async(std::launch::async, [&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        return batcher.Submit("face_detect", "req-3", 3, 40);
    });

    const auto batch_a = first.get();
    const auto batch_b = second.get();
    const auto batch_c = third.get();
    if (!Expect(batch_a.batch_size == 3, "full batch should contain three requests")) {
        return 1;
    }
    if (!Expect(batch_a.leader, "first request should become batch leader")) {
        return 1;
    }
    if (!Expect(batch_b.batch_index == 1, "second request batch index mismatch")) {
        return 1;
    }
    if (!Expect(batch_c.batch_index == 2, "third request batch index mismatch")) {
        return 1;
    }
    if (!Expect(!batch_a.timeout_triggered, "full batch should not be timeout triggered")) {
        return 1;
    }

    auto timeout_request = std::async(std::launch::async, [&]() {
        return batcher.Submit("ocr", "req-timeout", 4, 20);
    });
    const auto timeout_batch = timeout_request.get();
    if (!Expect(timeout_batch.batch_size == 1, "timeout batch should flush single request")) {
        return 1;
    }
    if (!Expect(timeout_batch.timeout_triggered, "timeout batch should report timeout trigger")) {
        return 1;
    }
    if (!Expect(timeout_batch.batch_wait_ms >= 15, "timeout batch should wait before flushing")) {
        return 1;
    }

    const auto face_metrics = batcher.GetCapabilityMetrics("face_detect");
    if (!Expect(face_metrics.has_value(), "batcher should expose capability metrics")) {
        return 1;
    }
    if (!Expect((*face_metrics)["formed_batch_count"] == 1, "face_detect formed batch count mismatch")) {
        return 1;
    }
    if (!Expect((*face_metrics)["full_flush_count"] == 1, "face_detect full flush count mismatch")) {
        return 1;
    }
    const auto ocr_metrics = batcher.GetCapabilityMetrics("ocr");
    if (!Expect(ocr_metrics.has_value(), "timeout capability metrics missing")) {
        return 1;
    }
    if (!Expect((*ocr_metrics)["timeout_flush_count"] == 1, "ocr timeout flush count mismatch")) {
        return 1;
    }

    return 0;
}
