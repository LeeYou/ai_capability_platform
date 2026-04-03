cmake_minimum_required(VERSION 3.20)
project(ai_prod_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(AI_PROD_CPP_BUILD_TESTS "Build ai-prod cpp tests" ON)

set(AI_PLATFORM_THIRD_PARTY_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../ai_platform/third_party")
set(AI_PLATFORM_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../ai_platform/include")

find_package(OpenSSL REQUIRED)
find_package(SQLite3 REQUIRED)

add_executable(ai_prod_cpp_proxy
    src/capability_catalog.cpp
    src/backend_client.cpp
    src/http_server.cpp
    src/instance_pool.cpp
    src/license_manager.cpp
    src/main.cpp
    src/plugin_executor.cpp
    src/proxy_config.cpp
    src/revision_store.cpp
    src/runtime_resource_scanner.cpp
    src/runtime_snapshot_manager.cpp
)

target_include_directories(ai_prod_cpp_proxy PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${AI_PLATFORM_INCLUDE_DIR}
    ${AI_PLATFORM_THIRD_PARTY_DIR}
)

target_link_libraries(ai_prod_cpp_proxy PRIVATE OpenSSL::Crypto SQLite::SQLite3 ${CMAKE_DL_LIBS})

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
        src/plugin_executor.cpp
        src/proxy_config.cpp
        src/revision_store.cpp
        src/runtime_resource_scanner.cpp
        src/runtime_snapshot_manager.cpp
    )

    target_include_directories(test_http_server PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_INCLUDE_DIR}
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_http_server PRIVATE OpenSSL::Crypto SQLite::SQLite3 ${CMAKE_DL_LIBS})

    add_test(NAME ai_prod_cpp_test_http_server COMMAND test_http_server)

    add_executable(test_runtime_components
        tests/test_runtime_components.cpp
        src/capability_catalog.cpp
        src/instance_pool.cpp
    )

    target_include_directories(test_runtime_components PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_INCLUDE_DIR}
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    add_test(NAME ai_prod_cpp_test_runtime_components COMMAND test_runtime_components)

    add_executable(test_runtime_transition_components
        tests/test_runtime_transition_components.cpp
        src/revision_store.cpp
        src/runtime_resource_scanner.cpp
    )

    target_include_directories(test_runtime_transition_components PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_INCLUDE_DIR}
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_runtime_transition_components PRIVATE SQLite::SQLite3)

    add_test(NAME ai_prod_cpp_test_runtime_transition_components COMMAND test_runtime_transition_components)

    add_library(test_mock_ai_plugin SHARED
        tests/test_mock_ai_plugin.cpp
    )

    target_include_directories(test_mock_ai_plugin PRIVATE
        ${AI_PLATFORM_INCLUDE_DIR}
    )

    add_dependencies(test_http_server test_mock_ai_plugin)

    add_executable(test_plugin_executor
        tests/test_plugin_executor.cpp
        src/plugin_executor.cpp
    )

    target_include_directories(test_plugin_executor PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_INCLUDE_DIR}
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_plugin_executor PRIVATE ${CMAKE_DL_LIBS})

    add_dependencies(test_plugin_executor test_mock_ai_plugin)

    add_test(NAME ai_prod_cpp_test_plugin_executor COMMAND test_plugin_executor)

    add_executable(test_license_manager
        tests/test_license_manager.cpp
        src/license_manager.cpp
    )

    target_include_directories(test_license_manager PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${AI_PLATFORM_INCLUDE_DIR}
        ${AI_PLATFORM_THIRD_PARTY_DIR}
    )

    target_link_libraries(test_license_manager PRIVATE OpenSSL::Crypto)

    add_test(NAME ai_prod_cpp_test_license_manager COMMAND test_license_manager)
endif()
