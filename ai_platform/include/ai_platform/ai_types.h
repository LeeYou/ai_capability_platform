#ifndef AI_PLATFORM_AI_TYPES_H
#define AI_PLATFORM_AI_TYPES_H

#include <cstdint>
#include <string>
#include <vector>

namespace ai_platform {

struct ImageData {
    std::vector<std::uint8_t> data;
    std::string format;
    std::string source;
};

struct MediaData {
    std::string media_type;
    std::vector<std::uint8_t> data;
    std::string format;
    std::string source;
    int frame_rate = 0;
};

struct InferRequest {
    std::string request_id;
    std::string capability_id;
    std::vector<ImageData> images;
    std::vector<MediaData> media;
    std::string params_json;
    std::int64_t timestamp = 0;
};

struct InferResult {
    int code = 0;
    std::string message;
    std::string data_json;
    std::string request_id;
    double cost_ms = 0.0;
};

}

#endif
