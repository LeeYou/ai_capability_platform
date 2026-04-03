#ifndef AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_TEST_LICENSE_HELPERS_H
#define AI_CAPABILITY_PLATFORM_APPS_AI_PROD_CPP_TEST_LICENSE_HELPERS_H

#include <openssl/evp.h>
#include <openssl/pem.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>

#include <nlohmann/json.hpp>

namespace test_license_helpers {

inline constexpr char kTestPrivateKeyPem[] =
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIKDQjKFaK+zFdxdS5MTPM3aNFBvsNwLjWN0skZw4cRHt\n"
    "-----END PRIVATE KEY-----\n";

inline constexpr char kTestPublicKeyPem[] =
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAvO4v5nAFm+1yb0D2iLxEtuZ/a0Nwb2jKzRnD3TpebSg=\n"
    "-----END PUBLIC KEY-----\n";

inline std::string JsonString(const std::string& value) {
    return nlohmann::json(value).dump();
}

inline std::string BuildCanonicalJson(const nlohmann::json& value) {
    if (value.is_object()) {
        std::vector<std::string> keys;
        keys.reserve(value.size());
        for (auto it = value.begin(); it != value.end(); ++it) {
            keys.push_back(it.key());
        }
        std::sort(keys.begin(), keys.end());

        std::ostringstream output;
        output << '{';
        for (std::size_t index = 0; index < keys.size(); ++index) {
            if (index > 0) {
                output << ',';
            }
            output << JsonString(keys[index]) << ':' << BuildCanonicalJson(value.at(keys[index]));
        }
        output << '}';
        return output.str();
    }
    if (value.is_array()) {
        std::ostringstream output;
        output << '[';
        for (std::size_t index = 0; index < value.size(); ++index) {
            if (index > 0) {
                output << ',';
            }
            output << BuildCanonicalJson(value[index]);
        }
        output << ']';
        return output.str();
    }
    return value.dump();
}

inline std::string Base64Encode(const std::string& raw_value) {
    if (raw_value.empty()) {
        return {};
    }
    std::string encoded(((raw_value.size() + 2) / 3) * 4, '\0');
    const int encoded_size = EVP_EncodeBlock(
        reinterpret_cast<unsigned char*>(encoded.data()),
        reinterpret_cast<const unsigned char*>(raw_value.data()),
        static_cast<int>(raw_value.size()));
    encoded.resize(static_cast<std::size_t>(encoded_size));
    return encoded;
}

inline std::string Sha256Hex(const std::string& input) {
    unsigned char digest[EVP_MAX_MD_SIZE] = {0};
    unsigned int digest_size = 0;
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    if (!context) {
        return {};
    }
    const bool ok =
        EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1 &&
        EVP_DigestUpdate(context, input.data(), input.size()) == 1 &&
        EVP_DigestFinal_ex(context, digest, &digest_size) == 1;
    EVP_MD_CTX_free(context);
    if (!ok) {
        return {};
    }
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (unsigned int index = 0; index < digest_size; ++index) {
        output << std::setw(2) << static_cast<int>(digest[index]);
    }
    return output.str();
}

inline std::string BuildHardwareFingerprint(const std::map<std::string, std::string>& features) {
    std::vector<std::pair<std::string, std::string>> normalized(features.begin(), features.end());
    std::sort(normalized.begin(), normalized.end(), [](const auto& left, const auto& right) {
        return left.first < right.first;
    });
    std::ostringstream output;
    for (std::size_t index = 0; index < normalized.size(); ++index) {
        if (index > 0) {
            output << '|';
        }
        std::string key = normalized[index].first;
        std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        output << key << '=' << normalized[index].second;
    }
    return Sha256Hex(output.str());
}

inline std::string SignPayload(const nlohmann::json& payload) {
    BIO* bio = BIO_new_mem_buf(kTestPrivateKeyPem, -1);
    EVP_PKEY* pkey = PEM_read_bio_PrivateKey(bio, nullptr, nullptr, nullptr);
    BIO_free(bio);
    if (!pkey) {
        return {};
    }

    EVP_MD_CTX* sign_context = EVP_MD_CTX_new();
    if (!sign_context) {
        EVP_PKEY_free(pkey);
        return {};
    }
    const std::string canonical_payload = BuildCanonicalJson(payload);
    std::size_t signature_size = 0;
    const bool ok =
        EVP_DigestSignInit(sign_context, nullptr, nullptr, nullptr, pkey) == 1 &&
        EVP_DigestSign(
            sign_context,
            nullptr,
            &signature_size,
            reinterpret_cast<const unsigned char*>(canonical_payload.data()),
            canonical_payload.size()) == 1;
    std::string signature(signature_size, '\0');
    const bool sign_ok =
        ok &&
        EVP_DigestSign(
            sign_context,
            reinterpret_cast<unsigned char*>(signature.data()),
            &signature_size,
            reinterpret_cast<const unsigned char*>(canonical_payload.data()),
            canonical_payload.size()) == 1;
    EVP_MD_CTX_free(sign_context);
    EVP_PKEY_free(pkey);
    if (!sign_ok) {
        return {};
    }
    signature.resize(signature_size);
    return Base64Encode(signature);
}

inline void WriteLicenseBundle(
    const std::filesystem::path& license_root,
    const nlohmann::json& payload,
    bool valid_signature = true) {
    std::filesystem::create_directories(license_root);
    nlohmann::json bundle = {
        {"algorithm", "ed25519"},
        {"payload", payload},
        {"signature", valid_signature ? SignPayload(payload) : "invalid-signature"},
    };
    std::ofstream license_output(license_root / "license.bin");
    license_output << bundle.dump();

    std::ofstream pubkey_output(license_root / "pubkey.pem");
    pubkey_output << kTestPublicKeyPem;
}

}

#endif
