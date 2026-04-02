#include "input_validators.h"
#include "license_common.h"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>

namespace {

constexpr int kValidationErrorCode = -400;

void assert_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << message << std::endl;
        std::exit(1);
    }
}

}

int main() {
    using ai_platform::InferRequestValidationSummary;
    using ai_platform::ImageFieldValidationSummary;
    using ai_platform::MediaFieldValidationSummary;
    using ai_platform::is_supported_local_uri;
    using ai_platform::is_valid_base64_text;
    using ai_platform::validate_image_fields;
    using ai_platform::validate_infer_request_summary;
    using ai_platform::validate_media_fields;

    assert_true(is_valid_base64_text("YWJjZA=="), "valid base64 should pass");
    assert_true(is_valid_base64_text("ZnJhbWUx"), "valid base64 without padding should pass");
    assert_true(!is_valid_base64_text(""), "empty base64 should fail");
    assert_true(!is_valid_base64_text("abc"), "invalid base64 length should fail");
    assert_true(!is_valid_base64_text("not-base64"), "invalid base64 chars should fail");
    assert_true(!is_valid_base64_text("YW=JjZA="), "invalid base64 padding position should fail");

    assert_true(is_supported_local_uri("demo.jpg"), "relative local path should pass");
    assert_true(is_supported_local_uri("C:/demo/video.mp4"), "windows local path should pass");
    assert_true(is_supported_local_uri("file:///tmp/demo.jpg"), "file uri should pass");
    assert_true(!is_supported_local_uri("http://example.com/demo.jpg"), "http uri should fail");
    assert_true(!is_supported_local_uri("https://example.com/demo.mp4"), "https uri should fail");
    assert_true(!is_supported_local_uri("ftp://example.com/demo.jpg"), "non-file scheme should fail");
    assert_true(!is_supported_local_uri(""), "empty uri should fail");

    ImageFieldValidationSummary valid_image_data;
    valid_image_data.has_format = true;
    valid_image_data.format = "jpg";
    valid_image_data.has_data = true;
    valid_image_data.data_text = "YWJjZA==";
    assert_true(validate_image_fields(valid_image_data).ok, "valid image data should pass");

    ImageFieldValidationSummary invalid_image_format;
    invalid_image_format.has_format = true;
    invalid_image_format.format = "gif";
    invalid_image_format.has_data = true;
    invalid_image_format.data_text = "YWJjZA==";
    assert_true(validate_image_fields(invalid_image_format).error_message == "unsupported image format", "unsupported image format should fail");
    assert_true(validate_image_fields(invalid_image_format).error_code == kValidationErrorCode, "unsupported image format error code should match");

    ImageFieldValidationSummary invalid_image_data;
    invalid_image_data.has_data = true;
    invalid_image_data.data_text = "not-base64";
    assert_true(validate_image_fields(invalid_image_data).error_message == "invalid image data", "invalid image data should fail");
    assert_true(validate_image_fields(invalid_image_data).error_code == kValidationErrorCode, "invalid image data error code should match");

    ImageFieldValidationSummary invalid_image_uri;
    invalid_image_uri.has_uri = true;
    invalid_image_uri.uri = "https://example.com/demo.jpg";
    assert_true(validate_image_fields(invalid_image_uri).error_message == "invalid image uri", "invalid image uri should fail");
    assert_true(validate_image_fields(invalid_image_uri).error_code == kValidationErrorCode, "invalid image uri error code should match");

    ImageFieldValidationSummary missing_image_input;
    assert_true(validate_image_fields(missing_image_input).error_message == "image data missing", "missing image input should fail");
    assert_true(validate_image_fields(missing_image_input).error_code == kValidationErrorCode, "missing image input error code should match");

    MediaFieldValidationSummary valid_media_data;
    valid_media_data.has_type = true;
    valid_media_data.media_type = "video";
    valid_media_data.has_format = true;
    valid_media_data.format = "mp4";
    valid_media_data.has_data = true;
    valid_media_data.data_text = "YWJjZA==";
    valid_media_data.max_data_bytes = 16;
    assert_true(validate_media_fields(valid_media_data).ok, "valid media data should pass");

    MediaFieldValidationSummary invalid_media_type;
    invalid_media_type.has_type = true;
    invalid_media_type.media_type = "audio";
    invalid_media_type.has_uri = true;
    invalid_media_type.uri = "file:///tmp/demo.mp4";
    assert_true(validate_media_fields(invalid_media_type).error_message == "unsupported media type", "unsupported media type should fail");
    assert_true(validate_media_fields(invalid_media_type).error_code == kValidationErrorCode, "unsupported media type error code should match");

    MediaFieldValidationSummary invalid_media_format;
    invalid_media_format.has_type = true;
    invalid_media_format.media_type = "video";
    invalid_media_format.has_format = true;
    invalid_media_format.format = "wmv";
    invalid_media_format.has_uri = true;
    invalid_media_format.uri = "file:///tmp/demo.wmv";
    assert_true(validate_media_fields(invalid_media_format).error_message == "unsupported media format", "unsupported media format should fail");
    assert_true(validate_media_fields(invalid_media_format).error_code == kValidationErrorCode, "unsupported media format error code should match");

    MediaFieldValidationSummary invalid_media_data;
    invalid_media_data.has_type = true;
    invalid_media_data.media_type = "video";
    invalid_media_data.has_data = true;
    invalid_media_data.data_text = "not-base64";
    invalid_media_data.max_data_bytes = 32;
    assert_true(validate_media_fields(invalid_media_data).error_message == "invalid media data", "invalid media data should fail");
    assert_true(validate_media_fields(invalid_media_data).error_code == kValidationErrorCode, "invalid media data error code should match");

    MediaFieldValidationSummary oversized_media_data;
    oversized_media_data.has_type = true;
    oversized_media_data.media_type = "video";
    oversized_media_data.has_data = true;
    oversized_media_data.data_text = "YWJjZA==";
    oversized_media_data.max_data_bytes = 4;
    assert_true(validate_media_fields(oversized_media_data).error_message == "media data too large", "oversized media data should fail");
    assert_true(validate_media_fields(oversized_media_data).error_code == kValidationErrorCode, "oversized media data error code should match");

    MediaFieldValidationSummary invalid_media_uri;
    invalid_media_uri.has_type = true;
    invalid_media_uri.media_type = "video";
    invalid_media_uri.has_uri = true;
    invalid_media_uri.uri = "https://example.com/demo.mp4";
    assert_true(validate_media_fields(invalid_media_uri).error_message == "invalid media uri", "invalid media uri should fail");
    assert_true(validate_media_fields(invalid_media_uri).error_code == kValidationErrorCode, "invalid media uri error code should match");

    MediaFieldValidationSummary missing_media_input;
    missing_media_input.has_type = true;
    missing_media_input.media_type = "video";
    assert_true(validate_media_fields(missing_media_input).error_message == "media data missing", "missing media input should fail");
    assert_true(validate_media_fields(missing_media_input).error_code == kValidationErrorCode, "missing media input error code should match");

    assert_true(!validate_infer_request_summary({}).ok, "missing media input should fail");
    assert_true(validate_infer_request_summary({}).error_code == kValidationErrorCode, "missing media input request error code should match");

    InferRequestValidationSummary face_summary;
    face_summary.capability_id = "face_detect";
    face_summary.image_count = 1;
    assert_true(validate_infer_request_summary(face_summary).ok, "basic face request should pass");

    InferRequestValidationSummary liveness_missing_params;
    liveness_missing_params.capability_id = "liveness_action";
    liveness_missing_params.media_count = 1;
    assert_true(validate_infer_request_summary(liveness_missing_params).error_message == "invalid liveness action params", "liveness missing params should fail");
    assert_true(validate_infer_request_summary(liveness_missing_params).error_code == kValidationErrorCode, "liveness missing params error code should match");

    InferRequestValidationSummary liveness_invalid_action;
    liveness_invalid_action.capability_id = "liveness_action";
    liveness_invalid_action.media_count = 1;
    liveness_invalid_action.has_params = true;
    liveness_invalid_action.liveness_action = "wave";
    assert_true(validate_infer_request_summary(liveness_invalid_action).error_message == "unsupported liveness action", "liveness invalid action should fail");
    assert_true(validate_infer_request_summary(liveness_invalid_action).error_code == kValidationErrorCode, "liveness invalid action error code should match");

    InferRequestValidationSummary liveness_single_image;
    liveness_single_image.capability_id = "liveness_action";
    liveness_single_image.image_count = 1;
    liveness_single_image.has_params = true;
    liveness_single_image.liveness_action = "blink";
    assert_true(validate_infer_request_summary(liveness_single_image).error_message == "liveness action requires video or frame sequence", "liveness single image should fail");
    assert_true(validate_infer_request_summary(liveness_single_image).error_code == kValidationErrorCode, "liveness single image error code should match");

    InferRequestValidationSummary liveness_video;
    liveness_video.capability_id = "liveness_action";
    liveness_video.media_count = 1;
    liveness_video.has_params = true;
    liveness_video.liveness_action = "blink";
    assert_true(validate_infer_request_summary(liveness_video).ok, "liveness video request should pass");

    InferRequestValidationSummary liveness_frame_sequence;
    liveness_frame_sequence.capability_id = "liveness_action";
    liveness_frame_sequence.image_count = 2;
    liveness_frame_sequence.has_params = true;
    liveness_frame_sequence.liveness_action = "nod";
    assert_true(validate_infer_request_summary(liveness_frame_sequence).ok, "liveness frame sequence should pass");

    _putenv("AI_PLATFORM_LICENSE_NOW=2026-03-02T06:00:00Z");
    ai_platform::LicenseFileData grace_license;
    grace_license.license_id = "LIC-GRACE-001";
    grace_license.version = "1.0";
    grace_license.license_type = "development";
    grace_license.customer_id = "CUST-GRACE-001";
    grace_license.customer_name = "demo_customer";
    grace_license.issued_at = "2026-03-01T00:00:00Z";
    grace_license.effective_from = "2026-03-01T00:00:00Z";
    grace_license.expires_at = "2026-03-02T00:00:00Z";
    grace_license.grace_period_hours = 24;
    grace_license.machine_fingerprint = ai_platform::compute_machine_fingerprint();
    grace_license.licensed_capabilities = {"face_detect"};
    grace_license.signature = ai_platform::build_license_signature(grace_license);
    std::string license_error_message;
    assert_true(ai_platform::verify_license_file(grace_license, ai_platform::compute_machine_fingerprint(), &license_error_message), "license should remain valid during grace period");
    _putenv("AI_PLATFORM_LICENSE_NOW=");

    return 0;
}
