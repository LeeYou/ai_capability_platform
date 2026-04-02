package ai.platform.sdk;

public final class LivenessActionJniDemo {
    private LivenessActionJniDemo() {
    }

    public static void main(String[] args) {
        if (args.length < 5) {
            throw new IllegalArgumentException("usage: LivenessActionJniDemo <jniLibraryName> <pluginPath> <modelDir> <mediaBase64> <action>");
        }

        LivenessActionJniBridge.loadLibrary(args[0]);
        String capabilityId = LivenessActionJniBridge.capabilityId(args[1], args[2]);
        String licenseFailureReason = LivenessActionJniBridge.lastLicenseFailureReason(args[1], args[2]);
        String licenseFailureDetail = LivenessActionJniBridge.lastLicenseFailureDetail(args[1], args[2]);
        String result = LivenessActionJniBridge.infer(args[1], args[2], args[3], "mp4", args[4]);

        System.out.println("capability_id=" + capabilityId);
        if (!licenseFailureReason.isEmpty()) {
            System.out.println("license_failure_reason=" + licenseFailureReason);
            System.out.println("license_failure_detail=" + licenseFailureDetail);
        }
        System.out.println(result);
    }
}
