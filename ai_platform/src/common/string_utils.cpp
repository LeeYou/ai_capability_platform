#include "string_utils.h"

namespace ai_platform {

std::string make_json_success(const std::string& payload) {
    return std::string{"{\"ok\":true,\"payload\":"} + payload + "}";
}

}
