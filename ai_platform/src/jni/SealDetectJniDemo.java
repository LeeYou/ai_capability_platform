package ai.platform.sdk;

public final class SealDetectJniDemo {
    private SealDetectJniDemo() {
    }

    public static void main(String[] args) {
        if (args.length < 4) {
            throw new IllegalArgumentException("usage: SealDetectJniDemo <jniLibraryName> <pluginPath> <modelDir> <imageBase64>");
        }

        SealDetectJniBridge.loadLibrary(args[0]);
        String capabilityId = SealDetectJniBridge.capabilityId(args[1], args[2]);
        String licenseFailureReason = SealDetectJniBridge.lastLicenseFailureReason(args[1], args[2]);
        String licenseFailureDetail = SealDetectJniBridge.lastLicenseFailureDetail(args[1], args[2]);
        String result = SealDetectJniBridge.infer(args[1], args[2], args[3], "jpg");

        System.out.println("capability_id=" + capabilityId);
        if (!licenseFailureReason.isEmpty()) {
            System.out.println("license_failure_reason=" + licenseFailureReason);
            System.out.println("license_failure_detail=" + licenseFailureDetail);
        }
        System.out.println(result);
    }
}
