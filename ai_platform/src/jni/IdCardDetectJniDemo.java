package ai.platform.sdk;

public final class IdCardDetectJniDemo {
    private IdCardDetectJniDemo() {
    }

    public static void main(String[] args) {
        if (args.length < 4) {
            throw new IllegalArgumentException("usage: IdCardDetectJniDemo <jniLibraryName> <pluginPath> <modelDir> <imageBase64>");
        }

        IdCardDetectJniBridge.loadLibrary(args[0]);
        String capabilityId = IdCardDetectJniBridge.capabilityId(args[1], args[2]);
        String licenseFailureReason = IdCardDetectJniBridge.lastLicenseFailureReason(args[1], args[2]);
        String licenseFailureDetail = IdCardDetectJniBridge.lastLicenseFailureDetail(args[1], args[2]);
        String result = IdCardDetectJniBridge.infer(args[1], args[2], args[3], "jpg");

        System.out.println("capability_id=" + capabilityId);
        if (!licenseFailureReason.isEmpty()) {
            System.out.println("license_failure_reason=" + licenseFailureReason);
            System.out.println("license_failure_detail=" + licenseFailureDetail);
        }
        System.out.println(result);
    }
}
