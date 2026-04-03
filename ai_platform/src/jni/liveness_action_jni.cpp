#include <jni.h>

#include "jni_bridge_common.h"
#include "liveness_action_sdk.h"

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

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_LivenessActionJniBridge_nativeVersion(JNIEnv* env, jclass) {
    return env->NewStringUTF(ai_platform::jni_bridge_version().c_str());
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_LivenessActionJniBridge_nativeCapabilityId(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::LivenessActionSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_error().c_str());
    }
    return env->NewStringUTF(sdk.capability_id().c_str());
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_LivenessActionJniBridge_nativeLastLicenseFailureReason(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::LivenessActionSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_license_failure_reason().c_str());
    }
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_LivenessActionJniBridge_nativeLastLicenseFailureDetail(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir) {
    ai_platform::LivenessActionSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_license_failure_detail().c_str());
    }
    return env->NewStringUTF("");
}

extern "C" JNIEXPORT jstring JNICALL Java_ai_platform_sdk_LivenessActionJniBridge_nativeInfer(JNIEnv* env, jclass, jstring pluginPath, jstring modelDir, jstring mediaBase64, jstring mediaFormat, jstring action) {
    ai_platform::LivenessActionSdk sdk;
    if (!sdk.initialize(to_std_string(env, pluginPath), to_std_string(env, modelDir))) {
        return env->NewStringUTF(sdk.last_error().c_str());
    }

    const auto infer_result = sdk.infer_video_base64(to_std_string(env, mediaBase64), to_std_string(env, mediaFormat), to_std_string(env, action));
    if (!infer_result.ok) {
        return env->NewStringUTF(infer_result.error_message.c_str());
    }

    return env->NewStringUTF(infer_result.result_json.c_str());
}
