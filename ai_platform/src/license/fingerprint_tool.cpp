#include "license_common.h"

#include <iostream>

int main() {
    std::cout << ai_platform::compute_machine_fingerprint() << std::endl;
    return 0;
}
