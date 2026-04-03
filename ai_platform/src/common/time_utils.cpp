#include "time_utils.h"

#include <chrono>

namespace ai_platform {

std::int64_t now_ms() {
    return static_cast<std::int64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count());
}

}
