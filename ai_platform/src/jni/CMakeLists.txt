find_package(JNI)
find_package(Java COMPONENTS Development)

add_library(ai_jni_bridge_common STATIC
    jni_bridge_common.cpp
)

target_include_directories(ai_jni_bridge_common PUBLIC
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}
)

if(JNI_FOUND)
    add_library(ai_jni_face_detect SHARED
        face_detect_jni.cpp
    )

    add_library(ai_jni_liveness_action SHARED
        liveness_action_jni.cpp
    )

    add_library(ai_jni_idcard_detect SHARED
        idcard_detect_jni.cpp
    )

    add_library(ai_jni_doc_classify SHARED
        doc_classify_jni.cpp
    )

    target_include_directories(ai_jni_face_detect PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        ${JNI_INCLUDE_DIRS}
    )

    target_include_directories(ai_jni_liveness_action PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        ${JNI_INCLUDE_DIRS}
    )

    target_include_directories(ai_jni_idcard_detect PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        ${JNI_INCLUDE_DIRS}
    )

    target_include_directories(ai_jni_doc_classify PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        ${JNI_INCLUDE_DIRS}
    )

    target_link_libraries(ai_jni_face_detect PRIVATE
        ai_jni_bridge_common
        ai_sdk_face_detect
    )

    target_link_libraries(ai_jni_liveness_action PRIVATE
        ai_jni_bridge_common
        ai_sdk_liveness_action
    )

    target_link_libraries(ai_jni_idcard_detect PRIVATE
        ai_jni_bridge_common
        ai_sdk_idcard_detect
    )

    target_link_libraries(ai_jni_doc_classify PRIVATE
        ai_jni_bridge_common
        ai_sdk_doc_classify
    )
    add_library(ai_jni_seal_detect SHARED
        seal_detect_jni.cpp
    )

    target_include_directories(ai_jni_seal_detect PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_SOURCE_DIR}/src/sdk/linux_so
        ${JNI_INCLUDE_DIRS}
    )

    target_link_libraries(ai_jni_seal_detect PRIVATE
        ai_jni_bridge_common
        ai_sdk_seal_detect
    )
endif()

if(Java_FOUND)
    set(AI_JNI_JAVA_SOURCES
        ${CMAKE_CURRENT_SOURCE_DIR}/FaceDetectJniBridge.java
        ${CMAKE_CURRENT_SOURCE_DIR}/FaceDetectJniDemo.java
        ${CMAKE_CURRENT_SOURCE_DIR}/LivenessActionJniBridge.java
        ${CMAKE_CURRENT_SOURCE_DIR}/LivenessActionJniDemo.java
        ${CMAKE_CURRENT_SOURCE_DIR}/IdCardDetectJniBridge.java
        ${CMAKE_CURRENT_SOURCE_DIR}/IdCardDetectJniDemo.java
        ${CMAKE_CURRENT_SOURCE_DIR}/DocClassifyJniBridge.java
        ${CMAKE_CURRENT_SOURCE_DIR}/DocClassifyJniDemo.java
        ${CMAKE_CURRENT_SOURCE_DIR}/SealDetectJniBridge.java
        ${CMAKE_CURRENT_SOURCE_DIR}/SealDetectJniDemo.java
    )
    set(AI_JNI_CLASSES_DIR ${CMAKE_CURRENT_BINARY_DIR}/java_classes)
    set(AI_JNI_JAR_PATH ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/$<CONFIG>/ai-capability-sdk.jar)

    add_custom_target(ai_capability_sdk_jar ALL
        COMMAND ${CMAKE_COMMAND} -E make_directory ${AI_JNI_CLASSES_DIR}
        COMMAND ${Java_JAVAC_EXECUTABLE} -d ${AI_JNI_CLASSES_DIR} ${AI_JNI_JAVA_SOURCES}
        COMMAND ${Java_JAR_EXECUTABLE} --create --file ${AI_JNI_JAR_PATH} -C ${AI_JNI_CLASSES_DIR} .
        DEPENDS ${AI_JNI_JAVA_SOURCES}
    )
endif()

