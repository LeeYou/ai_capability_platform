cmake_minimum_required(VERSION 3.20)
project(ai_prod_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(AI_PROD_CPP_BUILD_TESTS "Build ai-prod cpp tests" ON)

set(AI_PLATFORM_THIRD_PARTY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../ai_platform/third_party")

find_package(OpenSSL REQUIRED)

add_executable(ai_prod_cpp_proxy
    src/capability_catalog.cpp
    src/backend_client.cpp
    src/http_server.cpp
    src/instance_pool.cpp
    src/license_manager.cpp
    src/main.cpp
    src/proxy_config.cpp
    src/runtime_snapshot_manager.cpp
)

target_include_directories(ai_prod_cpp_proxy PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${AI_PLATFORM_THIRD_PARTY_DIR}
)

target_link_libraries(ai_prod_cpp_proxy PRIVATE OpenSSL::Crypto)

if(AI_PROD_CPP_BUILD_TESTS)
    enable_testing()

    add_executable(test_proxy_config
        tests/test_proxy_config.cpp
        src/proxy_config.cpp
    )

    target_include_directories(test_proxy_config PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    add_test(NAME ai_prod_cpp_test_proxy_config COMMAND test_proxy_config)

    add_executable(test_http_server
        src/capability_catalog.cpp
        tests/test_http_server.cpp
        src/backend_client.cpp
        src/http_server.cpp
        src/instance_pool.cpp
        src/license_manager.cpp
        src/proxy_config.cpp
        src/runtime_snapshot_manager.cpp
    )

    target_include_directories(test_http_server PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_http_server PRIVATE OpenSSL::Crypto)

    add_test(NAME ai_prod_cpp_test_http_server COMMAND test_http_server)

    add_executable(test_runtime_components
        tests/test_runtime_components.cpp
        src/capability_catalog.cpp
        src/instance_pool.cpp
    )

    target_include_directories(test_runtime_components PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    add_test(NAME ai_prod_cpp_test_runtime_components COMMAND test_runtime_components)

    add_executable(test_license_manager
        tests/test_license_manager.cpp
        src/license_manager.cpp
    )

    target_include_directories(test_license_manager PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_license_manager PRIVATE OpenSSL::Crypto)

    add_test(NAME ai_prod_cpp_test_license_manager COMMAND test_license_manager)
endif()
