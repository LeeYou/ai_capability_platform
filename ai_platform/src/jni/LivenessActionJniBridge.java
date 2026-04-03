package ai.platform.sdk;

public final class LivenessActionJniBridge {
    private LivenessActionJniBridge() {
    }

    public static void loadLibrary(String libraryName) {
        System.loadLibrary(libraryName);
    }

    public static native String nativeVersion();
    public static native String nativeCapabilityId(String pluginPath, String modelDir);
    public static native String nativeLastLicenseFailureReason(String pluginPath, String modelDir);
    public static native String nativeLastLicenseFailureDetail(String pluginPath, String modelDir);
    public static native String nativeInfer(String pluginPath, String modelDir, String mediaBase64, String mediaFormat, String action);

    public static String version() {
        return nativeVersion();
    }

    public static String capabilityId(String pluginPath, String modelDir) {
        return nativeCapabilityId(pluginPath, modelDir);
    }

    public static String lastLicenseFailureReason(String pluginPath, String modelDir) {
        return nativeLastLicenseFailureReason(pluginPath, modelDir);
    }

    public static String lastLicenseFailureDetail(String pluginPath, String modelDir) {
        return nativeLastLicenseFailureDetail(pluginPath, modelDir);
    }

    public static String infer(String pluginPath, String modelDir, String mediaBase64, String mediaFormat, String action) {
        return nativeInfer(pluginPath, modelDir, mediaBase64, mediaFormat, action);
    }
}
