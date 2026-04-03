#ifndef AI_PLATFORM_INPUT_VALIDATORS_H
#define AI_PLATFORM_INPUT_VALIDATORS_H

#include <cstddef>
#include <string>

namespace ai_platform {

struct InferRequestValidationSummary {
    std::string capability_id;
    std::size_t image_count = 0;
    std::size_t media_count = 0;
    bool has_params = false;
    std::string liveness_action;
};

struct ValidationResult {
    bool ok = false;
    int error_code = 0;
    std::string error_message;
};

struct ImageFieldValidationSummary {
    bool has_format = false;
    std::string format;
    bool has_data = false;
    std::string data_text;
    bool has_uri = false;
    std::string uri;
};

struct MediaFieldValidationSummary {
    bool has_type = false;
    std::string media_type;
    bool has_format = false;
    std::string format;
    bool has_data = false;
    std::string data_text;
    bool has_uri = false;
    std::string uri;
    std::size_t max_data_bytes = 0;
};

bool is_valid_base64_text(const std::string& value);
bool is_supported_local_uri(const std::string& value);
bool is_supported_image_format(const std::string& format);
bool is_supported_video_format(const std::string& format);
ValidationResult validate_image_fields(const ImageFieldValidationSummary& summary);
ValidationResult validate_media_fields(const MediaFieldValidationSummary& summary);
ValidationResult validate_infer_request_summary(const InferRequestValidationSummary& summary);

}

#endif
