package ai.platform.sdk;

public final class FaceDetectJniDemo {
    private FaceDetectJniDemo() {
    }

    public static void main(String[] args) {
        if (args.length < 4) {
            throw new IllegalArgumentException("usage: FaceDetectJniDemo <jniLibraryName> <pluginPath> <modelDir> <imageBase64>");
        }

        FaceDetectJniBridge.loadLibrary(args[0]);
        String capabilityId = FaceDetectJniBridge.capabilityId(args[1], args[2]);
        String licenseFailureReason = FaceDetectJniBridge.lastLicenseFailureReason(args[1], args[2]);
        String licenseFailureDetail = FaceDetectJniBridge.lastLicenseFailureDetail(args[1], args[2]);
        String result = FaceDetectJniBridge.infer(args[1], args[2], args[3], "jpg");

        System.out.println("capability_id=" + capabilityId);
        if (!licenseFailureReason.isEmpty()) {
            System.out.println("license_failure_reason=" + licenseFailureReason);
            System.out.println("license_failure_detail=" + licenseFailureDetail);
        }
        System.out.println(result);
    }
}
