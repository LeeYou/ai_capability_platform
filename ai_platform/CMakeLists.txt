cmake_minimum_required(VERSION 3.20)
project(ai_platform VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

foreach(CONFIG_TYPE Debug Release RelWithDebInfo MinSizeRel)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${CONFIG_TYPE} ${CMAKE_BINARY_DIR}/bin/${CONFIG_TYPE})
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_${CONFIG_TYPE} ${CMAKE_BINARY_DIR}/lib/${CONFIG_TYPE})
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_${CONFIG_TYPE} ${CMAKE_BINARY_DIR}/lib/${CONFIG_TYPE})
endforeach()

option(BUILD_SERVER "Build HTTP server" ON)
option(BUILD_PLUGINS "Build plugins" ON)
option(BUILD_TESTS "Build tests" OFF)
option(BUILD_JNI_WRAPPERS "Build JNI wrappers" OFF)
option(BUILD_WINDOWS_DLL "Build Windows DLL" OFF)
option(BUILD_SDK_ONLY "Build SDK only" OFF)

if(BUILD_TESTS)
    enable_testing()
endif()

add_subdirectory(src/common)
add_subdirectory(src/runtime)
add_subdirectory(src/license)
add_subdirectory(src/sdk)

if(BUILD_JNI_WRAPPERS)
    add_subdirectory(src/jni)
endif()

if(BUILD_SERVER)
    add_subdirectory(src/server)
endif()

if(BUILD_PLUGINS)
    add_subdirectory(src/plugins)
endif()

if(BUILD_TESTS)
    add_subdirectory(tests)
endif()
