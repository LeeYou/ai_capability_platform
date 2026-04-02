add_executable(ai_platform_server
    main.cpp
    ai_http_server.cpp
)

target_include_directories(ai_platform_server PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/third_party
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/runtime
    ${CMAKE_SOURCE_DIR}/src/license
)

target_link_libraries(ai_platform_server PRIVATE
    ai_runtime
    ai_license
    ai_common
)
