cmake_minimum_required(VERSION 3.18)
project(face_detect_plugin LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ONNX Runtime 推理后端（生产环境启用: cmake -DONNXRUNTIME_ENABLED=ON -DONNXRUNTIME_ROOT_DIR=...)
option(ONNXRUNTIME_ENABLED "启用 ONNX Runtime 推理后端" OFF)
set(ONNXRUNTIME_ROOT_DIR "" CACHE PATH "ONNX Runtime 安装根目录")

# 平台公共头文件
set(AI_PLATFORM_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../include" CACHE PATH "ai_platform 公共头文件目录")

add_library(face_detect_plugin SHARED
    src/face_detect_plugin.cpp
)

target_include_directories(face_detect_plugin PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${AI_PLATFORM_INCLUDE_DIR}
)

if(ONNXRUNTIME_ENABLED)
    if(NOT ONNXRUNTIME_ROOT_DIR STREQUAL "")
        target_include_directories(face_detect_plugin PRIVATE "${ONNXRUNTIME_ROOT_DIR}/include")
        target_link_directories(face_detect_plugin PRIVATE "${ONNXRUNTIME_ROOT_DIR}/lib")
    endif()
    find_library(ONNXRUNTIME_LIB onnxruntime
        HINTS "${ONNXRUNTIME_ROOT_DIR}/lib" "${ONNXRUNTIME_ROOT_DIR}/lib64"
    )
    if(ONNXRUNTIME_LIB)
        target_link_libraries(face_detect_plugin PRIVATE ${ONNXRUNTIME_LIB})
    else()
        target_link_libraries(face_detect_plugin PRIVATE onnxruntime)
    endif()
    target_compile_definitions(face_detect_plugin PRIVATE ONNXRUNTIME_ENABLED)
    message(STATUS "[face_detect_plugin] ONNX Runtime 已启用")
else()
    message(STATUS "[face_detect_plugin] ONNX Runtime 未启用，使用仿真模式")
endif()

set_target_properties(face_detect_plugin PROPERTIES
    OUTPUT_NAME "face_detect_plugin"
    PREFIX ""
)

install(TARGETS face_detect_plugin
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(FILES include/face_detect_plugin.h DESTINATION include)
