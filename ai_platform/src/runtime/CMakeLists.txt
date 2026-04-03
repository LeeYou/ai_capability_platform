add_library(ai_runtime STATIC
    ai_runtime.cpp
    capability_pool.cpp
    plugin_manager.cpp
    pool_manager.cpp
    reload_controller.cpp
)

target_include_directories(ai_runtime PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src/common
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(ai_runtime PUBLIC
    ai_common
)
