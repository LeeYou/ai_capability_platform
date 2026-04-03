#include <jni.h>

#include "jni_bridge_common.h"
#include "face_detect_sdk.h"

#include <string>

namespace {

std::string to_std_string(JNIEnv* env, jstring value) {
    if (!value) {
        return std::string();
    }
    const char* chars = env->GetStringUTFChars(value, nullptr);
    if (!chars) {
        return std::string();
    }
    std::string result(chars);
    env->ReleaseStringUTFChars(value, chars);
    return result;
}

}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_FaceDetectJniBridge_nativeVersion(JNIEnv* env, jclass) {
    return env->NewStringUTF(ai_platform::jni_bridge_version().c_str());
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_FaceDetectJniBridge_nativeCapabilityId(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::FaceDetectSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_error().c_str());
    }
    return env->NewStringUTF(sdk.capability_id().c_str());
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_FaceDetectJniBridge_nativeLastLicenseFailureReason(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::FaceDetectSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_license_failure_reason().c_str());
    }
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_FaceDetectJniBridge_nativeLastLicenseFailureDetail(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::FaceDetectSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_license_failure_detail().c_str());
    }
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_FaceDetectJniBridge_nativeInfer(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir, jstring imageBase64, jstring imageFormat) {
    ai_platform::FaceDetectSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_error().c_str());
    }

    const auto infer_result = sdk.infer_image_base64(to_std_string(env, imageBase64), to_std_string(env, imageFormat));
    if (!infer_result.ok) {
        return env->NewStringUTF(infer_result.error_message.c_str());
    }

    return env->NewStringUTF(infer_result.result_json.c_str());
}
