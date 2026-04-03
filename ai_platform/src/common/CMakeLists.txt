add_library(ai_common STATIC
    app_paths.cpp
    input_validators.cpp
    model_package.cpp
    platform_config.cpp
    string_utils.cpp
    time_utils.cpp
)

target_include_directories(ai_common PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)
