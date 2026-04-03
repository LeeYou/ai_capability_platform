#include "input_validators.h"

#include <cctype>

namespace ai_platform {

namespace {

constexpr int kValidationErrorCode = -400;

bool starts_with(const std::string& value, const std::string& prefix) {
    return value.rfind(prefix, 0) == 0;
}

bool is_supported_liveness_action(const std::string& action) {
    return action == "blink" || action == "mouth" || action == "shake_head" || action == "nod";
}

}

bool is_valid_base64_text(const std::string& value) {
    if (value.empty() || (value.size() % 4) != 0) {
        return false;
    }

    bool seen_padding = false;
    for (std::size_t i = 0; i < value.size(); ++i) {
        const unsigned char ch = static_cast<unsigned char>(value[i]);
        const bool is_base64_char = std::isalnum(ch) != 0 || ch == '+' || ch == '/';
        if (ch == '=') {
            if (i < value.size() - 2) {
                return false;
            }
            seen_padding = true;
            continue;
        }
        if (!is_base64_char || seen_padding) {
            return false;
        }
    }

    return true;
}

bool is_supported_image_format(const std::string& format) {
    return format == "jpeg" || format == "jpg" || format == "png" || format == "bmp";
}

bool is_supported_video_format(const std::string& format) {
    return format == "mp4" || format == "avi" || format == "mov";
}

bool is_supported_local_uri(const std::string& value) {
    if (value.empty()) {
        return false;
    }
    if (starts_with(value, "http://") || starts_with(value, "https://")) {
        return false;
    }
    const auto scheme_pos = value.find("://");
    if (scheme_pos != std::string::npos) {
        return starts_with(value, "file://");
    }
    return true;
}

ValidationResult validate_image_fields(const ImageFieldValidationSummary& summary) {
    if (summary.has_format) {
        if (summary.format.empty()) {
            return {false, kValidationErrorCode, "invalid image format"};
        }
        if (!is_supported_image_format(summary.format)) {
            return {false, kValidationErrorCode, "unsupported image format"};
        }
    }

    if (summary.has_data && !is_valid_base64_text(summary.data_text)) {
        return {false, kValidationErrorCode, "invalid image data"};
    }

    if (!summary.has_data && summary.has_uri && !is_supported_local_uri(summary.uri)) {
        return {false, kValidationErrorCode, "invalid image uri"};
    }

    if (!summary.has_data && !summary.has_uri) {
        return {false, kValidationErrorCode, "image data missing"};
    }

    return {true, 0, ""};
}

ValidationResult validate_media_fields(const MediaFieldValidationSummary& summary) {
    if (!summary.has_type || summary.media_type.empty()) {
        return {false, kValidationErrorCode, "invalid media type"};
    }
    if (summary.media_type != "video") {
        return {false, kValidationErrorCode, "unsupported media type"};
    }

    if (summary.has_format) {
        if (summary.format.empty()) {
            return {false, kValidationErrorCode, "invalid media format"};
        }
        if (!is_supported_video_format(summary.format)) {
            return {false, kValidationErrorCode, "unsupported media format"};
        }
    }

    if (summary.has_data) {
        if (!is_valid_base64_text(summary.data_text)) {
            return {false, kValidationErrorCode, "invalid media data"};
        }
        if (summary.data_text.size() > summary.max_data_bytes) {
            return {false, kValidationErrorCode, "media data too large"};
        }
    }

    if (!summary.has_data && summary.has_uri && !is_supported_local_uri(summary.uri)) {
        return {false, kValidationErrorCode, "invalid media uri"};
    }

    if (!summary.has_data && !summary.has_uri) {
        return {false, kValidationErrorCode, "media data missing"};
    }

    return {true, 0, ""};
}

ValidationResult validate_infer_request_summary(const InferRequestValidationSummary& summary) {
    if (summary.image_count == 0 && summary.media_count == 0) {
        return {false, kValidationErrorCode, "missing media input"};
    }

    if (summary.capability_id == "liveness_action") {
        if (!summary.has_params || summary.liveness_action.empty()) {
            return {false, kValidationErrorCode, "invalid liveness action params"};
        }
        if (!is_supported_liveness_action(summary.liveness_action)) {
            return {false, kValidationErrorCode, "unsupported liveness action"};
        }
        const bool has_video_input = summary.media_count > 0;
        const bool has_frame_sequence_input = summary.image_count >= 2;
        if (!has_video_input && !has_frame_sequence_input) {
            return {false, kValidationErrorCode, "liveness action requires video or frame sequence"};
        }
    }

    return {true, 0, ""};
}

}
