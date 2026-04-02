macro(add_capability_plugin PLUGIN_NAME)
    add_library(cap_${PLUGIN_NAME} SHARED
        ${PLUGIN_NAME}/${PLUGIN_NAME}_plugin.cpp
    )

    target_include_directories(cap_${PLUGIN_NAME} PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_SOURCE_DIR}/third_party
    )

    set_target_properties(cap_${PLUGIN_NAME} PROPERTIES
        OUTPUT_NAME "cap_${PLUGIN_NAME}"
        PREFIX "lib"
    )
endmacro()

add_capability_plugin(face_detect)
add_capability_plugin(liveness_action)
add_capability_plugin(idcard_detect)
add_capability_plugin(doc_classify)

add_capability_plugin(seal_detect)

