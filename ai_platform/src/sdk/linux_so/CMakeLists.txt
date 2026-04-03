add_library(ai_sdk_face_detect STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    face_detect_sdk.cpp
)

add_library(ai_sdk_liveness_action STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    liveness_action_sdk.cpp
)

add_library(ai_sdk_idcard_detect STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    idcard_detect_sdk.cpp
)

add_library(ai_sdk_doc_classify STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    doc_classify_sdk.cpp
)

target_include_directories(ai_sdk_face_detect PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_liveness_action PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_idcard_detect PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_doc_classify PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_face_detect PRIVATE
    ai_license
)

target_link_libraries(ai_sdk_liveness_action PRIVATE
    ai_license
)

target_link_libraries(ai_sdk_idcard_detect PRIVATE
    ai_license
)

target_link_libraries(ai_sdk_doc_classify PRIVATE
    ai_license
)

add_executable(ai_sdk_face_detect_sample
    face_detect_sdk_sample.cpp
)

add_executable(test_face_detect_sdk
    test_face_detect_sdk.cpp
)

add_executable(ai_sdk_liveness_action_sample
    liveness_action_sdk_sample.cpp
)

add_executable(test_liveness_action_sdk
    test_liveness_action_sdk.cpp
)

add_executable(ai_sdk_idcard_detect_sample
    idcard_detect_sdk_sample.cpp
)

add_executable(test_idcard_detect_sdk
    test_idcard_detect_sdk.cpp
)

add_executable(ai_sdk_doc_classify_sample
    doc_classify_sdk_sample.cpp
)

add_executable(test_doc_classify_sdk
    test_doc_classify_sdk.cpp
)

target_include_directories(ai_sdk_face_detect_sample PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_face_detect_sdk PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_liveness_action_sample PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_liveness_action_sdk PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_idcard_detect_sample PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_idcard_detect_sdk PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(ai_sdk_doc_classify_sample PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_doc_classify_sdk PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_face_detect_sample PRIVATE
    ai_sdk_face_detect
)

target_link_libraries(test_face_detect_sdk PRIVATE
    ai_sdk_face_detect
    ai_license
)

target_link_libraries(ai_sdk_liveness_action_sample PRIVATE
    ai_sdk_liveness_action
)

target_link_libraries(test_liveness_action_sdk PRIVATE
    ai_sdk_liveness_action
    ai_license
)

target_link_libraries(ai_sdk_idcard_detect_sample PRIVATE
    ai_sdk_idcard_detect
)

target_link_libraries(test_idcard_detect_sdk PRIVATE
    ai_sdk_idcard_detect
    ai_license
)

target_link_libraries(ai_sdk_doc_classify_sample PRIVATE
    ai_sdk_doc_classify
)

target_link_libraries(test_doc_classify_sdk PRIVATE
    ai_sdk_doc_classify
    ai_license
)

add_test(
    NAME test_face_detect_sdk
    COMMAND test_face_detect_sdk
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_face_detect.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_liveness_action_sdk
    COMMAND test_liveness_action_sdk
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_liveness_action.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_idcard_detect_sdk
    COMMAND test_idcard_detect_sdk
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_idcard_detect.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_doc_classify_sdk
    COMMAND test_doc_classify_sdk
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_doc_classify.dll
        ${CMAKE_SOURCE_DIR}
)

add_library(ai_sdk_seal_detect STATIC
    capability_sdk.cpp
    sdk_loader.cpp
    seal_detect_sdk.cpp
)

target_include_directories(ai_sdk_seal_detect PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_seal_detect PRIVATE
    ai_license
)

add_executable(ai_sdk_seal_detect_sample
    seal_detect_sdk_sample.cpp
)

add_executable(test_seal_detect_sdk
    test_seal_detect_sdk.cpp
)

target_include_directories(ai_sdk_seal_detect_sample PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_seal_detect_sdk PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_sdk_seal_detect_sample PRIVATE
    ai_sdk_seal_detect
)

target_link_libraries(test_seal_detect_sdk PRIVATE
    ai_sdk_seal_detect
    ai_license
)

add_test(
    NAME test_seal_detect_sdk
    COMMAND test_seal_detect_sdk
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_seal_detect.dll
        ${CMAKE_SOURCE_DIR}
)

