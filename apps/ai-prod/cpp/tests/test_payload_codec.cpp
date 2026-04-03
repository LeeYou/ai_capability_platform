#include "payload_codec.h"

#include <iostream>
#include <string>

namespace {

bool Expect(bool condition, const char* message) {
    if (!condition) {
        std::cerr << message << std::endl;
        return false;
    }
    return true;
}

}  // namespace

int main() {
    DecodedPayload decoded_payload;
    std::string error_message;

    if (!Expect(
            PayloadCodec::Decode("json", "{\"demo\":true}", &decoded_payload, &error_message),
            "json payload should pass through codec")) {
        return 1;
    }
    if (!Expect(decoded_payload.normalized_payload == "{\"demo\":true}", "json payload should remain unchanged")) {
        return 1;
    }

    if (!Expect(
            PayloadCodec::Decode("image", "iVBORw0KGgo=", &decoded_payload, &error_message),
            "png payload should decode successfully")) {
        return 1;
    }
    if (!Expect(decoded_payload.metadata["detected_format"] == "png", "png payload should expose detected format")) {
        return 1;
    }

    if (!Expect(
            PayloadCodec::Decode("video", "AAAAGGZ0eXBpc29t", &decoded_payload, &error_message),
            "mp4 payload should decode successfully")) {
        return 1;
    }
    if (!Expect(decoded_payload.metadata["detected_format"] == "mp4", "video payload should expose mp4 format")) {
        return 1;
    }

    if (!Expect(
            PayloadCodec::Decode("pdf", "JVBERi0xLjQK", &decoded_payload, &error_message),
            "pdf payload should decode successfully")) {
        return 1;
    }
    if (!Expect(decoded_payload.metadata["detected_format"] == "pdf", "pdf payload should expose detected format")) {
        return 1;
    }

    if (!Expect(
            !PayloadCodec::Decode("image", "demo-ocr", &decoded_payload, &error_message),
            "invalid base64 image payload should be rejected")) {
        return 1;
    }
    if (!Expect(error_message == "image payload 不是合法 base64。", "invalid image should report base64 error")) {
        return 1;
    }

    if (!Expect(
            !PayloadCodec::Decode("pdf", "aGVsbG8=", &decoded_payload, &error_message),
            "non-pdf binary payload should be rejected")) {
        return 1;
    }
    if (!Expect(error_message == "pdf payload 不是合法 PDF 数据。", "invalid pdf should report format error")) {
        return 1;
    }

    return 0;
}
