add_library(ai_license STATIC
    license_common.cpp
    license_manager.cpp
)

target_include_directories(ai_license PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_license PUBLIC
    ai_common
)

add_executable(fingerprint_tool
    fingerprint_tool.cpp
)

target_include_directories(fingerprint_tool PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(fingerprint_tool PRIVATE
    ai_license
)

add_executable(license_tool
    license_tool.cpp
)

target_include_directories(license_tool PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(license_tool PRIVATE
    ai_license
)

add_custom_command(TARGET license_tool POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/tmp
    COMMAND $<TARGET_FILE:license_tool> generate ${CMAKE_BINARY_DIR}/tmp/demo_license.dat demo_customer face_detect,liveness_action,not_exist_cap
    COMMENT "Generating demo license"
)
