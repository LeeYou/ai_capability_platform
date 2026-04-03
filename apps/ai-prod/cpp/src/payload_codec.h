#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PAYLOAD_CODEC_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_PAYLOAD_CODEC_H

#include <nlohmann/json.hpp>

#include <string>

struct DecodedPayload {
    std::string normalized_payload;
    nlohmann::json metadata = nlohmann::json::object();
};

class PayloadCodec {
public:
    static bool Decode(
        const std::string& input_type,
        const std::string& payload,
        DecodedPayload* decoded_payload,
        std::string* error_message);

private:
    static bool DecodeBinaryPayload(
        const std::string& input_type,
        const std::string& payload,
        DecodedPayload* decoded_payload,
        std::string* error_message);
    static bool ValidateMagicBytes(
        const std::string& input_type,
        const std::string& binary_payload,
        DecodedPayload* decoded_payload,
        std::string* error_message);
};

#endif
