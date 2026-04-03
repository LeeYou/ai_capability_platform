package ai.platform.sdk;

public final class FaceDetectJniBridge {
    private FaceDetectJniBridge() {
    }

    public static void loadLibrary(String libraryName) {
        System.loadLibrary(libraryName);
    }

    public static native String nativeVersion();
    public static native String nativeCapabilityId(String pluginPath, String modelDir);
    public static native String nativeLastLicenseFailureReason(String pluginPath, String modelDir);
    public static native String nativeLastLicenseFailureDetail(String pluginPath, String modelDir);
    public static native String nativeInfer(String pluginPath, String modelDir, String imageBase64, String imageFormat);

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

    public static String infer(String pluginPath, String modelDir, String imageBase64, String imageFormat) {
        return nativeInfer(pluginPath, modelDir, imageBase64, imageFormat);
    }
}
