# 05 — C++ 推理插件 SO 设计

## 5.1 设计原则

1. **标准 C ABI** — 所有导出接口使用 `extern "C"`，确保跨编译器二进制兼容
2. **生命周期明确** — init → infer → reload → destroy，每个阶段职责清晰
3. **内存所有权清晰** — 谁分配谁释放，通过专用释放函数回收内存
4. **线程安全** — 每个 handle 独立，无共享可变全局状态
5. **错误码统一** — 所有插件使用同一套错误码体系
6. **自描述** — 插件可报告自身能力名、版本、模型信息
7. **交付形态复用** — 同一能力内核同时支撑 Linux SO、JNI、Windows DLL 等交付形态
8. **跨平台可编译** — 代码避免平台强绑定，编译阶段按平台适配导出格式

## 5.2 公共头文件 (ai_plugin_api.h)

这是所有插件必须实现的标准接口定义：

```c
// ai_plugin_api.h — AI 能力插件标准 C ABI 接口
// 所有插件必须实现此头文件中声明的全部接口

#ifndef AI_PLUGIN_API_H
#define AI_PLUGIN_API_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================
// 版本信息
// ============================================================
#define AI_PLUGIN_API_VERSION_MAJOR 1
#define AI_PLUGIN_API_VERSION_MINOR 0
#define AI_PLUGIN_API_VERSION_PATCH 0

// ============================================================
// 错误码定义
// ============================================================
typedef enum {
    AI_SUCCESS                  = 0,      // 成功
    AI_ERROR_UNKNOWN            = -1,     // 未知错误
    AI_ERROR_INVALID_PARAM      = -2,     // 参数无效
    AI_ERROR_INVALID_HANDLE     = -3,     // 句柄无效
    AI_ERROR_INIT_FAILED        = -4,     // 初始化失败
    AI_ERROR_MODEL_LOAD_FAILED  = -5,     // 模型加载失败
    AI_ERROR_INFER_FAILED       = -6,     // 推理失败
    AI_ERROR_IMAGE_DECODE       = -7,     // 图像解码失败
    AI_ERROR_OUT_OF_MEMORY      = -8,     // 内存不足
    AI_ERROR_NOT_INITIALIZED    = -9,     // 未初始化
    AI_ERROR_ALREADY_INIT       = -10,    // 重复初始化
    AI_ERROR_RELOAD_FAILED      = -11,    // 重新加载失败
    AI_ERROR_TIMEOUT            = -12,    // 超时
    AI_ERROR_DEVICE_ERROR       = -13,    // 设备(GPU)错误
    AI_ERROR_CHECKSUM_MISMATCH  = -14,    // 校验和不匹配
    AI_ERROR_LICENSE_INVALID    = -15,    // 授权无效
    AI_ERROR_UNSUPPORTED        = -16,    // 不支持的操作
} AiErrorCode;

// ============================================================
// 设备类型
// ============================================================
typedef enum {
    AI_DEVICE_CPU   = 0,
    AI_DEVICE_CUDA  = 1,
} AiDeviceType;

// ============================================================
// 图像格式
// ============================================================
typedef enum {
    AI_IMAGE_FORMAT_BGR     = 0,  // OpenCV 默认 BGR
    AI_IMAGE_FORMAT_RGB     = 1,
    AI_IMAGE_FORMAT_GRAY    = 2,
    AI_IMAGE_FORMAT_ENCODED = 3,  // JPEG/PNG 编码数据
} AiImageFormat;

// ============================================================
// 媒体类型
// ============================================================
typedef enum {
    AI_MEDIA_TYPE_IMAGE          = 0,
    AI_MEDIA_TYPE_VIDEO          = 1,
    AI_MEDIA_TYPE_FRAME_SEQUENCE = 2,
} AiMediaType;

// ============================================================
// 数据结构定义
// ============================================================

// 不透明句柄
typedef void* AiPluginHandle;

// 初始化参数
typedef struct {
    const char*   model_dir;        // 模型目录路径
    AiDeviceType  device;           // 设备类型
    int           device_id;        // GPU ID (CUDA 模式)
    int           max_batch_size;   // 最大批量大小
    const char*   extra_config;     // 额外配置 (JSON 字符串, 可为 NULL)
    int           log_level;        // 日志级别 0=off,1=error,2=warn,3=info,4=debug
} AiPluginInitParams;

// 输入图像
typedef struct {
    const uint8_t*  data;           // 图像数据指针
    int             width;          // 宽度 (ENCODED 格式时为 0)
    int             height;         // 高度 (ENCODED 格式时为 0)
    int             channels;       // 通道数 (ENCODED 格式时为 0)
    int             stride;         // 行步长 (字节数, ENCODED 格式时为 0)
    size_t          data_size;      // 数据总字节数
    AiImageFormat   format;         // 图像格式
} AiImage;

// 推理输入
typedef struct {
    const AiImage*  images;         // 图像数组
    int             image_count;    // 图像数量
    const uint8_t*  media_data;     // 扩展媒体原始数据 (视频文件等)
    size_t          media_size;     // 媒体数据大小
    AiMediaType     media_type;     // 媒体类型
    const char*     media_format;   // "mp4", "avi", "h264" 等
    const char*     params_json;    // 额外参数 (JSON 字符串, 可为 NULL)
} AiPluginInput;

// 推理输出 (由插件分配，Runtime 通过 free_result 释放)
typedef struct {
    char*           result_json;    // 结果 JSON 字符串 (插件分配)
    int             result_code;    // 结果状态码
    const char*     error_message;  // 错误消息 (失败时, 插件内部静态字符串)
    double          infer_time_ms;  // 纯推理耗时 (毫秒)
} AiPluginOutput;

// 能力信息
typedef struct {
    const char*     capability_id;    // 能力标识
    const char*     capability_name;  // 能力显示名
    const char*     version;          // 插件版本
    const char*     model_version;    // 当前模型版本
    const char*     description;      // 描述
    int             api_version_major;
    int             api_version_minor;
    int             api_version_patch;
    AiDeviceType    current_device;   // 当前使用的设备
    const char*     extra_info_json;  // 额外信息 (JSON)
} AiPluginInfo;

// ============================================================
// 插件必须导出的接口函数
// ============================================================

// --- 生命周期 ---

// 创建并初始化一个插件实例
// 成功返回 AI_SUCCESS，handle 通过 out_handle 输出
// 一个 SO 可创建多个独立 handle (用于实例池)
typedef AiErrorCode (*fn_ai_plugin_init)(
    const AiPluginInitParams* params,
    AiPluginHandle* out_handle
);

// 销毁插件实例，释放所有资源
typedef AiErrorCode (*fn_ai_plugin_destroy)(
    AiPluginHandle handle
);

// --- 推理 ---

// 执行推理
// output 由插件内部分配，调用方需通过 ai_plugin_free_result 释放
typedef AiErrorCode (*fn_ai_plugin_infer)(
    AiPluginHandle handle,
    const AiPluginInput* input,
    AiPluginOutput* output
);

// 释放推理结果内存
typedef void (*fn_ai_plugin_free_result)(
    AiPluginOutput* output
);

// --- 管理 ---

// 重新加载模型 (热更新)
// new_model_dir 为新模型目录，为 NULL 则重新加载当前模型
typedef AiErrorCode (*fn_ai_plugin_reload)(
    AiPluginHandle handle,
    const char* new_model_dir
);

// 获取插件/能力信息
// info 指向调用方提供的结构体，由插件填充
// 内部指针指向插件内部静态存储，调用方不得释放
typedef AiErrorCode (*fn_ai_plugin_get_info)(
    AiPluginHandle handle,
    AiPluginInfo* info
);

// --- 可选接口 ---

// 预热 (执行一次空推理以初始化 GPU 资源)
typedef AiErrorCode (*fn_ai_plugin_warmup)(
    AiPluginHandle handle
);

// 健康检查
typedef AiErrorCode (*fn_ai_plugin_health_check)(
    AiPluginHandle handle
);

// ============================================================
// 导出宏定义
// ============================================================

#ifdef _WIN32
  #define AI_PLUGIN_EXPORT __declspec(dllexport)
#else
  #define AI_PLUGIN_EXPORT __attribute__((visibility("default")))
#endif

// 每个插件 SO 必须导出以下符号名:
//   ai_plugin_init
//   ai_plugin_destroy
//   ai_plugin_infer
//   ai_plugin_free_result
//   ai_plugin_reload
//   ai_plugin_get_info
//   ai_plugin_warmup        (可选)
//   ai_plugin_health_check  (可选)

#define AI_PLUGIN_DECLARE_FUNCTIONS() \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_init( \
        const AiPluginInitParams* params, AiPluginHandle* out_handle); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_destroy( \
        AiPluginHandle handle); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_infer( \
        AiPluginHandle handle, const AiPluginInput* input, \
        AiPluginOutput* output); \
    AI_PLUGIN_EXPORT void ai_plugin_free_result( \
        AiPluginOutput* output); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_reload( \
        AiPluginHandle handle, const char* new_model_dir); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_get_info( \
        AiPluginHandle handle, AiPluginInfo* info); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_warmup( \
        AiPluginHandle handle); \
    AI_PLUGIN_EXPORT AiErrorCode ai_plugin_health_check( \
        AiPluginHandle handle);

#ifdef __cplusplus
}
#endif

#endif // AI_PLUGIN_API_H
```

## 5.2.1 交付形态与二进制产物

统一插件接口对应的交付产物如下：

| 交付形态 | 产物 | 说明 |
|---------|------|------|
| Linux 平台版 | `libcap_xxx.so` | 供 Docker 平台或 C/C++ SDK 调用 |
| Java 集成版 | `libcap_xxx.so` + `libai_jni_xxx.so` + `jar` | JNI 包装层调用能力插件 |
| Windows 集成版 | `cap_xxx.dll` + `cap_xxx.lib` | 单能力 DLL 交付 |
| ARM 平台版 | `libcap_xxx.so` | 在 ARM64 目标环境重新编译 |

其中：

- **能力内核代码尽量共享**。
- **JNI/DLL 只作为外层适配层**，不复制推理逻辑。
- **模型包规范不因交付形态变化而变化**。

## 5.3 插件实现模板

每个插件 SO 的典型实现结构：

```cpp
// 示例: plugins/face_detect/face_detect_plugin.cpp

#include "ai_plugin_api.h"
#include <onnxruntime_cxx_api.h>
#include <opencv2/opencv.hpp>
#include <string>
#include <memory>
#include <mutex>

// ============================================================
// 内部上下文 (每个 handle 独立)
// ============================================================
struct FaceDetectContext {
    std::unique_ptr<Ort::Session> session;
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "face_detect"};
    Ort::MemoryInfo memory_info = Ort::MemoryInfo::CreateCpu(
        OrtArenaAllocator, OrtMemTypeDefault);
    
    // 模型参数
    std::string model_dir;
    int input_width = 640;
    int input_height = 640;
    float conf_threshold = 0.5f;
    float nms_threshold = 0.4f;
    AiDeviceType device = AI_DEVICE_CPU;
    
    // 工作缓冲区 (handle 独占，无需加锁)
    cv::Mat preprocess_buf;
    std::vector<float> input_tensor_buf;
    
    // 信息
    std::string version = "1.0.0";
    std::string model_version;
    bool initialized = false;
};

// ============================================================
// 内部辅助函数
// ============================================================
static AiErrorCode load_model(FaceDetectContext* ctx) {
    try {
        Ort::SessionOptions session_opts;
        session_opts.SetGraphOptimizationLevel(
            GraphOptimizationLevel::ORT_ENABLE_ALL);
        
        if (ctx->device == AI_DEVICE_CUDA) {
            OrtCUDAProviderOptions cuda_opts;
            cuda_opts.device_id = 0;
            session_opts.AppendExecutionProvider_CUDA(cuda_opts);
        }
        
        std::string model_path = ctx->model_dir + "/model.onnx";
        ctx->session = std::make_unique<Ort::Session>(
            ctx->env, model_path.c_str(), session_opts);
        
        return AI_SUCCESS;
    } catch (const Ort::Exception& e) {
        return AI_ERROR_MODEL_LOAD_FAILED;
    }
}

static AiErrorCode load_config(FaceDetectContext* ctx) {
    // 从 model_dir/config.yaml 加载预处理参数、阈值等
    // ... 省略 YAML 解析细节
    return AI_SUCCESS;
}

// ============================================================
// 导出接口实现
// ============================================================
extern "C" {

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_init(
    const AiPluginInitParams* params,
    AiPluginHandle* out_handle)
{
    if (!params || !out_handle) return AI_ERROR_INVALID_PARAM;
    if (!params->model_dir) return AI_ERROR_INVALID_PARAM;
    
    auto* ctx = new (std::nothrow) FaceDetectContext();
    if (!ctx) return AI_ERROR_OUT_OF_MEMORY;
    
    ctx->model_dir = params->model_dir;
    ctx->device = params->device;
    
    // 加载配置
    AiErrorCode rc = load_config(ctx);
    if (rc != AI_SUCCESS) {
        delete ctx;
        return rc;
    }
    
    // 加载模型
    rc = load_model(ctx);
    if (rc != AI_SUCCESS) {
        delete ctx;
        return rc;
    }
    
    ctx->initialized = true;
    *out_handle = static_cast<AiPluginHandle>(ctx);
    return AI_SUCCESS;
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_destroy(AiPluginHandle handle) {
    if (!handle) return AI_ERROR_INVALID_HANDLE;
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    ctx->session.reset();
    delete ctx;
    return AI_SUCCESS;
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_infer(
    AiPluginHandle handle,
    const AiPluginInput* input,
    AiPluginOutput* output)
{
    if (!handle) return AI_ERROR_INVALID_HANDLE;
    if (!input || !output) return AI_ERROR_INVALID_PARAM;
    if (input->image_count < 1) return AI_ERROR_INVALID_PARAM;
    
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    if (!ctx->initialized) return AI_ERROR_NOT_INITIALIZED;
    
    auto start = std::chrono::high_resolution_clock::now();
    
    // 1. 解码图像
    cv::Mat image;
    const AiImage& img = input->images[0];
    if (img.format == AI_IMAGE_FORMAT_ENCODED) {
        std::vector<uint8_t> buf(img.data, img.data + img.data_size);
        image = cv::imdecode(buf, cv::IMREAD_COLOR);
    } else {
        image = cv::Mat(img.height, img.width, CV_8UC3, 
                       const_cast<uint8_t*>(img.data), img.stride);
    }
    if (image.empty()) {
        output->result_code = AI_ERROR_IMAGE_DECODE;
        output->error_message = "Failed to decode image";
        output->result_json = nullptr;
        return AI_ERROR_IMAGE_DECODE;
    }
    
    // 2. 预处理
    cv::resize(image, ctx->preprocess_buf, 
               cv::Size(ctx->input_width, ctx->input_height));
    // ... normalize, hwc2chw 等
    
    // 3. 推理
    // ... ONNX Runtime session->Run()
    
    // 4. 后处理 (NMS, 阈值过滤)
    // ... 得到检测结果
    
    // 5. 构建 JSON 结果
    // 使用 snprintf 或简单拼接避免引入额外 JSON 库依赖
    std::string result = R"({"faces":[)";
    // ... 拼接检测到的人脸
    result += "]}";
    
    auto end = std::chrono::high_resolution_clock::now();
    double cost = std::chrono::duration<double, std::milli>(end - start).count();
    
    // 6. 填充输出 (分配内存)
    output->result_json = new char[result.size() + 1];
    std::memcpy(output->result_json, result.c_str(), result.size() + 1);
    output->result_code = AI_SUCCESS;
    output->error_message = nullptr;
    output->infer_time_ms = cost;
    
    return AI_SUCCESS;
}

AI_PLUGIN_EXPORT void ai_plugin_free_result(AiPluginOutput* output) {
    if (output && output->result_json) {
        delete[] output->result_json;
        output->result_json = nullptr;
    }
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_reload(
    AiPluginHandle handle, const char* new_model_dir)
{
    if (!handle) return AI_ERROR_INVALID_HANDLE;
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    
    std::string dir = new_model_dir ? new_model_dir : ctx->model_dir;
    
    // 保存旧 session
    auto old_session = std::move(ctx->session);
    ctx->model_dir = dir;
    
    // 尝试加载新模型
    AiErrorCode rc = load_model(ctx);
    if (rc != AI_SUCCESS) {
        // 回滚
        ctx->session = std::move(old_session);
        return AI_ERROR_RELOAD_FAILED;
    }
    
    // 成功，旧 session 自动释放
    return AI_SUCCESS;
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_get_info(
    AiPluginHandle handle, AiPluginInfo* info)
{
    if (!handle || !info) return AI_ERROR_INVALID_PARAM;
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    
    info->capability_id = "face_detect";
    info->capability_name = "人脸检测";
    info->version = ctx->version.c_str();
    info->model_version = ctx->model_version.c_str();
    info->description = "Detect faces in images, return bounding boxes and landmarks";
    info->api_version_major = AI_PLUGIN_API_VERSION_MAJOR;
    info->api_version_minor = AI_PLUGIN_API_VERSION_MINOR;
    info->api_version_patch = AI_PLUGIN_API_VERSION_PATCH;
    info->current_device = ctx->device;
    info->extra_info_json = nullptr;
    
    return AI_SUCCESS;
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_warmup(AiPluginHandle handle) {
    if (!handle) return AI_ERROR_INVALID_HANDLE;
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    
    // 构造一张小图进行空推理，预热 GPU
    cv::Mat dummy = cv::Mat::zeros(ctx->input_height, ctx->input_width, CV_8UC3);
    AiImage img = {};
    img.data = dummy.data;
    img.width = dummy.cols;
    img.height = dummy.rows;
    img.channels = 3;
    img.stride = static_cast<int>(dummy.step);
    img.data_size = dummy.total() * dummy.elemSize();
    img.format = AI_IMAGE_FORMAT_BGR;
    
    AiPluginInput input = { &img, 1, nullptr };
    AiPluginOutput output = {};
    
    AiErrorCode rc = ai_plugin_infer(handle, &input, &output);
    ai_plugin_free_result(&output);
    
    return rc;
}

AI_PLUGIN_EXPORT AiErrorCode ai_plugin_health_check(AiPluginHandle handle) {
    if (!handle) return AI_ERROR_INVALID_HANDLE;
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    if (!ctx->initialized || !ctx->session) return AI_ERROR_NOT_INITIALIZED;
    return AI_SUCCESS;
}

} // extern "C"
```

## 5.4 CMake 工程结构

### 5.4.1 顶层 CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.20)
project(ai_platform VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ---- 选项 ----
option(BUILD_SERVER "Build HTTP server" ON)
option(BUILD_PLUGINS "Build all capability plugins" ON)
option(BUILD_TESTS "Build tests" OFF)
option(ENABLE_CUDA "Enable CUDA support" ON)
option(BUILD_JNI_WRAPPERS "Build JNI wrappers" OFF)
option(BUILD_WINDOWS_DLL "Build Windows DLL packages" OFF)
option(BUILD_SDK_ONLY "Build SDK without HTTP server" OFF)

# ---- 依赖查找 ----
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)
find_package(OpenSSL REQUIRED)
find_package(yaml-cpp REQUIRED)

# ONNX Runtime
if(NOT ONNXRUNTIME_DIR)
    set(ONNXRUNTIME_DIR "/opt/onnxruntime" CACHE PATH "ONNX Runtime directory")
endif()
find_library(ONNXRUNTIME_LIB onnxruntime HINTS ${ONNXRUNTIME_DIR}/lib)
set(ONNXRUNTIME_INCLUDE ${ONNXRUNTIME_DIR}/include)

# ---- 公共接口库 ----
add_library(ai_plugin_api INTERFACE)
target_include_directories(ai_plugin_api INTERFACE
    ${CMAKE_SOURCE_DIR}/include
    ${ONNXRUNTIME_INCLUDE}
)

# ---- 公共工具库 ----
add_subdirectory(src/common)

# ---- Runtime 库 ----
add_subdirectory(src/runtime)

# ---- HTTP 服务 ----
if(BUILD_SERVER)
    add_subdirectory(src/server)
endif()

if(BUILD_JNI_WRAPPERS)
    add_subdirectory(src/jni)
endif()

# ---- 插件 ----
if(BUILD_PLUGINS)
    add_subdirectory(src/plugins)
endif()

# ---- 授权模块 ----
add_subdirectory(src/license)

# ---- 测试 ----
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# ---- 安装规则 ----
install(TARGETS ai_platform_server DESTINATION app/bin)
install(DIRECTORY ${CMAKE_SOURCE_DIR}/config/ DESTINATION app/config)
```

### 5.4.2 插件 CMake 模板

```cmake
# src/plugins/CMakeLists.txt

# 插件构建宏 — 所有插件统一用此宏构建
macro(add_capability_plugin PLUGIN_NAME)
    add_library(cap_${PLUGIN_NAME} SHARED
        ${PLUGIN_NAME}_plugin.cpp
        ${ARGN}  # 额外源文件
    )
    
    target_link_libraries(cap_${PLUGIN_NAME} PRIVATE
        ai_plugin_api
        ai_common
        ${OpenCV_LIBS}
        ${ONNXRUNTIME_LIB}
        yaml-cpp
    )
    
    target_include_directories(cap_${PLUGIN_NAME} PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${ONNXRUNTIME_INCLUDE}
    )
    
    # SO 文件命名: libcap_xxx.so
    set_target_properties(cap_${PLUGIN_NAME} PROPERTIES
        OUTPUT_NAME "cap_${PLUGIN_NAME}"
        PREFIX "lib"
        SUFFIX ".so"
        VERSION ${PROJECT_VERSION}
        SOVERSION ${PROJECT_VERSION_MAJOR}
    )
    
    # 控制符号可见性
    set_target_properties(cap_${PLUGIN_NAME} PROPERTIES
        CXX_VISIBILITY_PRESET hidden
        C_VISIBILITY_PRESET hidden
    )
    
    install(TARGETS cap_${PLUGIN_NAME} DESTINATION app/plugins)
endmacro()

# ---- 构建各能力插件 ----
add_subdirectory(face_detect)
add_subdirectory(face_recognize)
add_subdirectory(liveness_action)
add_subdirectory(liveness_silent)
add_subdirectory(face_attribute)
add_subdirectory(idcard_detect)
add_subdirectory(doc_classify)
add_subdirectory(handwriting_recognize)
add_subdirectory(business_license_ocr)
add_subdirectory(seal_detect)
add_subdirectory(seal_recognize)
add_subdirectory(invoice_ocr)
add_subdirectory(electricity_bill_ocr)
add_subdirectory(contract_ocr)
add_subdirectory(recapture_detect)
add_subdirectory(deepfake_detect)
add_subdirectory(general_ocr)
```

### 5.4.4 跨平台构建策略

```cmake
if(WIN32)
    set(PLUGIN_BINARY_SUFFIX ".dll")
elseif(UNIX)
    set(PLUGIN_BINARY_SUFFIX ".so")
endif()

if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|ARM64")
    add_definitions(-DAI_PLATFORM_ARM64=1)
endif()
```

约束：

- Linux 下默认构建 `.so`
- Windows 下默认构建 `.dll + .lib`
- JNI 构建本质为额外桥接库，不替代插件本体

## 5.4.5 JNI 适配层设计

JNI 适配层职责：

1. 接收 Java 层参数。
2. 转换为 `AiPluginInput`。
3. 调用能力插件。
4. 将 JSON 结果返回 Java。

建议产物：

- `ai-capability-sdk.jar`
- `libai_jni_face_detect.so`
- `libcap_face_detect.so`
- `models/face_detect/...`

## 5.4.6 Windows DLL 适配层设计

Windows 交付形态不包含 HTTP 服务，仅包含：

- `cap_xxx.dll`
- `cap_xxx.lib`
- `cap_xxx.h`
- `models/<capability>/...`
- `license.dat`

Windows 导出接口仍保持标准 C ABI，避免名称修饰和 C++ ABI 问题。

### 5.4.3 单个插件 CMakeLists.txt 示例

```cmake
# src/plugins/face_detect/CMakeLists.txt

add_capability_plugin(face_detect
    # 可添加额外源文件
    # nms.cpp
    # preprocess.cpp
)
```

## 5.5 并发安全规范

### 5.5.1 实例隔离保证

每个 `AiPluginHandle` 对应一个独立的 `Context` 对象，包含：

| 资源 | 隔离方式 |
|------|---------|
| ONNX Session | 每个 handle 独立 Session (或共享 Session + 独立 RunOptions) |
| 预处理缓冲区 | handle 内部独占 cv::Mat |
| 输入张量缓冲区 | handle 内部独占 vector |
| 后处理临时变量 | 函数局部变量 |

### 5.5.2 禁止事项

```
[MUST NOT] 使用可变的全局/静态变量
[MUST NOT] 在 infer 中修改共享状态
[MUST NOT] 返回指向内部临时缓冲区的指针
[MUST NOT] 在 result_json 中使用 static 缓冲区
[MUST NOT] 在没有同步的情况下共享 ONNX Session
```

### 5.5.3 ONNX Runtime 线程安全策略

```
方案 A (推荐): 每个 handle 独立 Session
  - 优点: 完全无锁，最简单
  - 缺点: 显存占用略高
  - 适用: GPU 显存充裕时

方案 B: 共享 Session + 独立 RunOptions  
  - 优点: 节省显存
  - 缺点: ONNX Runtime Session.Run() 内部有锁
  - 适用: GPU 显存紧张时

配置项: session_sharing = false (默认 A) | true (切换到 B)
```

## 5.6 插件开发规范检查清单

开发新插件前，对照此检查清单：

- [ ] 所有导出函数使用 `extern "C"` + `AI_PLUGIN_EXPORT`
- [ ] `ai_plugin_init` 中所有资源分配有对应的 `ai_plugin_destroy` 释放
- [ ] `ai_plugin_infer` 中 `result_json` 使用 `new char[]` 分配
- [ ] `ai_plugin_free_result` 正确释放 `result_json`
- [ ] 无全局可变状态
- [ ] 无 `static` 局部可变变量
- [ ] `ai_plugin_reload` 失败时能回滚到旧模型
- [ ] `ai_plugin_get_info` 返回的指针指向 handle 内部存储或字面量
- [ ] 输出 JSON 格式正确，使用 UTF-8 编码
- [ ] 所有异常被捕获，不抛出到 C ABI 边界外
