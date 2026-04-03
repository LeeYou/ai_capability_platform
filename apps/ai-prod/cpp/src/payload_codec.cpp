#include "payload_codec.h"

#include <openssl/evp.h>

#include <algorithm>
#include <cctype>
#include <optional>

namespace {

std::optional<std::string> Base64Decode(const std::string& encoded_value) {
    if (encoded_value.empty()) {
        return std::string();
    }
    std::string compact;
    compact.reserve(encoded_value.size());
    for (char ch : encoded_value) {
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            compact.push_back(ch);
        }
    }
    if (compact.empty()) {
        return std::string();
    }

    const std::size_t padding =
        compact.size() >= 2 && compact.compare(compact.size() - 2, 2, "==") == 0 ? 2 :
        (compact.size() >= 1 && compact.back() == '=' ? 1 : 0);
    std::string decoded((compact.size() * 3) / 4 + 4, '\0');
    const int decoded_size = EVP_DecodeBlock(
        reinterpret_cast<unsigned char*>(decoded.data()),
        reinterpret_cast<const unsigned char*>(compact.data()),
        static_cast<int>(compact.size()));
    if (decoded_size < 0) {
        return std::nullopt;
    }
    decoded.resize(static_cast<std::size_t>(decoded_size) - padding);
    return decoded;
}

bool StartsWith(const std::string& value, const std::string& prefix) {
    return value.size() >= prefix.size() &&
           std::equal(prefix.begin(), prefix.end(), value.begin());
}

}  // namespace

bool PayloadCodec::Decode(
    const std::string& input_type,
    const std::string& payload,
    DecodedPayload* decoded_payload,
    std::string* error_message) {
    if (decoded_payload == nullptr) {
        if (error_message != nullptr) {
            *error_message = "输入 payload codec 输出对象不能为空。";
        }
        return false;
    }
    if (input_type == "json") {
        decoded_payload->normalized_payload = payload;
        decoded_payload->metadata = {
            {"encoding", "utf-8"},
            {"transport", "plain_text"},
            {"decoded_size", payload.size()},
        };
        return true;
    }
    return DecodeBinaryPayload(input_type, payload, decoded_payload, error_message);
}

bool PayloadCodec::DecodeBinaryPayload(
    const std::string& input_type,
    const std::string& payload,
    DecodedPayload* decoded_payload,
    std::string* error_message) {
    const auto decoded = Base64Decode(payload);
    if (!decoded.has_value()) {
        if (error_message != nullptr) {
            *error_message = input_type + " payload 不是合法 base64。";
        }
        return false;
    }
    if (decoded->empty()) {
        if (error_message != nullptr) {
            *error_message = input_type + " payload 解码后为空。";
        }
        return false;
    }
    decoded_payload->normalized_payload = *decoded;
    decoded_payload->metadata = {
        {"encoding", "base64"},
        {"decoded_size", decoded->size()},
    };
    return ValidateMagicBytes(input_type, *decoded, decoded_payload, error_message);
}

bool PayloadCodec::ValidateMagicBytes(
    const std::string& input_type,
    const std::string& binary_payload,
    DecodedPayload* decoded_payload,
    std::string* error_message) {
    if (input_type == "image") {
        if (StartsWith(binary_payload, "\x89PNG\r\n\x1a\n")) {
            decoded_payload->metadata["detected_format"] = "png";
            return true;
        }
        if (StartsWith(binary_payload, "\xff\xd8\xff")) {
            decoded_payload->metadata["detected_format"] = "jpeg";
            return true;
        }
        if (error_message != nullptr) {
            *error_message = "image payload 不是受支持的 PNG/JPEG 数据。";
        }
        return false;
    }
    if (input_type == "video") {
        if (binary_payload.size() >= 8 && binary_payload.compare(4, 4, "ftyp") == 0) {
            decoded_payload->metadata["detected_format"] = "mp4";
            return true;
        }
        if (error_message != nullptr) {
            *error_message = "video payload 不是受支持的 MP4 数据。";
        }
        return false;
    }
    if (input_type == "pdf") {
        if (StartsWith(binary_payload, "%PDF-")) {
            decoded_payload->metadata["detected_format"] = "pdf";
            return true;
        }
        if (error_message != nullptr) {
            *error_message = "pdf payload 不是合法 PDF 数据。";
        }
        return false;
    }
    if (error_message != nullptr) {
        *error_message = "input_type 不受支持。";
    }
    return false;
}
