add_library(ai_sdk_windows_exports STATIC
    dll_exports.cpp
)

target_include_directories(ai_sdk_windows_exports PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

add_library(ai_face_detect_sdk SHARED
    face_detect_dll.cpp
)

add_library(ai_liveness_action_sdk SHARED
    liveness_action_dll.cpp
)

add_library(ai_idcard_detect_sdk SHARED
    idcard_detect_dll.cpp
)

add_library(ai_doc_classify_sdk SHARED
    doc_classify_dll.cpp
)

target_include_directories(ai_face_detect_sdk PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_include_directories(ai_liveness_action_sdk PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_include_directories(ai_idcard_detect_sdk PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_include_directories(ai_doc_classify_sdk PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_link_libraries(ai_face_detect_sdk PRIVATE
    ai_sdk_face_detect
)

target_link_libraries(ai_liveness_action_sdk PRIVATE
    ai_sdk_liveness_action
)

target_link_libraries(ai_idcard_detect_sdk PRIVATE
    ai_sdk_idcard_detect
)

target_link_libraries(ai_doc_classify_sdk PRIVATE
    ai_sdk_doc_classify
)

add_executable(face_detect_dll_sample
    face_detect_dll_sample.cpp
)

target_include_directories(face_detect_dll_sample PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(face_detect_dll_sample PRIVATE
    ai_face_detect_sdk
)

add_executable(test_face_detect_dll
    test_face_detect_dll.cpp
)

add_executable(liveness_action_dll_sample
    liveness_action_dll_sample.cpp
)

add_executable(test_liveness_action_dll
    test_liveness_action_dll.cpp
)

add_executable(idcard_detect_dll_sample
    idcard_detect_dll_sample.cpp
)

add_executable(test_idcard_detect_dll
    test_idcard_detect_dll.cpp
)

add_executable(doc_classify_dll_sample
    doc_classify_dll_sample.cpp
)

add_executable(test_doc_classify_dll
    test_doc_classify_dll.cpp
)

target_include_directories(test_face_detect_dll PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(liveness_action_dll_sample PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_liveness_action_dll PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(idcard_detect_dll_sample PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_idcard_detect_dll PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(doc_classify_dll_sample PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_doc_classify_dll PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(test_face_detect_dll PRIVATE
    ai_face_detect_sdk
    ai_license
)

target_link_libraries(liveness_action_dll_sample PRIVATE
    ai_liveness_action_sdk
)

target_link_libraries(test_liveness_action_dll PRIVATE
    ai_liveness_action_sdk
    ai_license
)

target_link_libraries(idcard_detect_dll_sample PRIVATE
    ai_idcard_detect_sdk
)

target_link_libraries(test_idcard_detect_dll PRIVATE
    ai_idcard_detect_sdk
    ai_license
)

target_link_libraries(doc_classify_dll_sample PRIVATE
    ai_doc_classify_sdk
)

target_link_libraries(test_doc_classify_dll PRIVATE
    ai_doc_classify_sdk
    ai_license
)

add_test(
    NAME test_face_detect_dll
    COMMAND test_face_detect_dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_face_detect.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_liveness_action_dll
    COMMAND test_liveness_action_dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_liveness_action.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_idcard_detect_dll
    COMMAND test_idcard_detect_dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_idcard_detect.dll
        ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME test_doc_classify_dll
    COMMAND test_doc_classify_dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_doc_classify.dll
        ${CMAKE_SOURCE_DIR}
)

add_library(ai_seal_detect_sdk SHARED
    seal_detect_dll.cpp
)

target_include_directories(ai_seal_detect_sdk PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
)

target_link_libraries(ai_seal_detect_sdk PRIVATE
    ai_sdk_seal_detect
)

add_executable(seal_detect_dll_sample
    seal_detect_dll_sample.cpp
)

add_executable(test_seal_detect_dll
    test_seal_detect_dll.cpp
)

target_include_directories(seal_detect_dll_sample PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(test_seal_detect_dll PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(seal_detect_dll_sample PRIVATE
    ai_seal_detect_sdk
)

target_link_libraries(test_seal_detect_dll PRIVATE
    ai_seal_detect_sdk
    ai_license
)

add_test(
    NAME test_seal_detect_dll
    COMMAND test_seal_detect_dll
        ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/libcap_seal_detect.dll
        ${CMAKE_SOURCE_DIR}
)

