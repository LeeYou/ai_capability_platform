package ai.platform.sdk;

public final class DocClassifyJniDemo {
    private DocClassifyJniDemo() {
    }

    public static void main(String[] args) {
        if (args.length < 4) {
            throw new IllegalArgumentException("usage: DocClassifyJniDemo <jniLibraryName> <pluginPath> <modelDir> <imageBase64>");
        }

        DocClassifyJniBridge.loadLibrary(args[0]);
        String capabilityId = DocClassifyJniBridge.capabilityId(args[1], args[2]);
        String licenseFailureReason = DocClassifyJniBridge.lastLicenseFailureReason(args[1], args[2]);
        String licenseFailureDetail = DocClassifyJniBridge.lastLicenseFailureDetail(args[1], args[2]);
        String result = DocClassifyJniBridge.infer(args[1], args[2], args[3], "jpg");

        System.out.println("capability_id=" + capabilityId);
        if (!licenseFailureReason.isEmpty()) {
            System.out.println("license_failure_reason=" + licenseFailureReason);
            System.out.println("license_failure_detail=" + licenseFailureDetail);
        }
        System.out.println(result);
    }
}
