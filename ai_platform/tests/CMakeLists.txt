enable_testing()

add_executable(test_input_validators
    test_input_validators.cpp
)

add_executable(test_platform_config
    test_platform_config.cpp
)

add_executable(test_plugin_manager
    test_plugin_manager.cpp
)

add_executable(test_reload_controller
    test_reload_controller.cpp
)

add_executable(test_license_manager
    test_license_manager.cpp
)

target_include_directories(test_input_validators PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_SOURCE_DIR}/src/license
)

target_include_directories(test_platform_config PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_SOURCE_DIR}/src/license
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_plugin_manager PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_SOURCE_DIR}/src/license
    ${CMAKE_SOURCE_DIR}/src/runtime
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_reload_controller PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_SOURCE_DIR}/src/license
    ${CMAKE_SOURCE_DIR}/src/runtime
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_license_manager PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_SOURCE_DIR}/src/license
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(test_input_validators PRIVATE
    ai_common
    ai_license
)

target_link_libraries(test_platform_config PRIVATE
    ai_common
    ai_license
)

target_link_libraries(test_plugin_manager PRIVATE
    ai_common
    ai_runtime
    ai_license
)

target_link_libraries(test_reload_controller PRIVATE
    ai_common
    ai_runtime
    ai_license
)

target_link_libraries(test_license_manager PRIVATE
    ai_common
    ai_license
)

add_test(NAME test_input_validators COMMAND test_input_validators)

add_test(NAME test_platform_config COMMAND test_platform_config)

add_test(
    NAME test_plugin_manager
    COMMAND test_plugin_manager
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_face_detect.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_liveness_action.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_idcard_detect.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_doc_classify.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_seal_detect.dll
)

add_test(
    NAME test_reload_controller
    COMMAND test_reload_controller
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_face_detect.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_liveness_action.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_idcard_detect.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_doc_classify.dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_seal_detect.dll
)

add_test(NAME test_license_manager COMMAND test_license_manager)

add_test(
    NAME test_delivery_acceptance
    COMMAND powershell
        -NoProfile
        -ExecutionPolicy Bypass
        -File ${CMAKE_SOURCE_DIR}/scripts/run_delivery_ctest_entry.ps1
        -Mode acceptance
        -SourceRoot ${CMAKE_SOURCE_DIR}
        -BuildConfig $<CONFIG>
)
set_tests_properties(test_delivery_acceptance PROPERTIES
    SKIP_RETURN_CODE 125
    LABELS "delivery_acceptance;optional"
)

add_test(
    NAME test_delivery_acceptance_matrix
    COMMAND powershell
        -NoProfile
        -ExecutionPolicy Bypass
        -File ${CMAKE_SOURCE_DIR}/scripts/run_delivery_ctest_entry.ps1
        -Mode matrix
        -SourceRoot ${CMAKE_SOURCE_DIR}
        -BuildConfig $<CONFIG>
)
set_tests_properties(test_delivery_acceptance_matrix PROPERTIES
    SKIP_RETURN_CODE 125
    LABELS "delivery_acceptance;optional;matrix"
)
