/**
 * face_detect 人脸检测推理插件实现
 *
 * 基于 YOLOv8n ONNX 模型实现人脸检测，遵循 ai_plugin_api.h C ABI。
 * 编译时通过 ONNXRUNTIME_ENABLED 宏控制真实推理 / 仿真模式。
 *
 * 推理流程:
 *   1. ai_plugin_init: 加载 ONNX 模型到 ORT Session
 *   2. ai_plugin_infer: 预处理 → 推理 → NMS 后处理 → JSON 输出
 *   3. ai_plugin_destroy: 释放资源
 */

#include "face_detect_plugin.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <new>
#include <numeric>
#include <sstream>
#include <string>
#include <vector>

#ifdef ONNXRUNTIME_ENABLED
#include <onnxruntime_cxx_api.h>
#endif

namespace {

// ── YOLOv8n 常量 ──
constexpr int kInputWidth = 640;
constexpr int kInputHeight = 640;
constexpr int kInputChannels = 3;
constexpr float kDefaultScoreThreshold = 0.5f;
constexpr float kDefaultNmsThreshold = 0.45f;

struct Detection {
    float x1, y1, x2, y2;
    float score;
    int class_id;
};

// ── 插件上下文 ──
struct FaceDetectContext {
    std::string model_dir;
    AiDeviceType device = AI_DEVICE_CPU;
    int max_batch_size = 1;
    float score_threshold = kDefaultScoreThreshold;
    float nms_threshold = kDefaultNmsThreshold;
#ifdef ONNXRUNTIME_ENABLED
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "face_detect"};
    std::unique_ptr<Ort::Session> session;
    Ort::AllocatorWithDefaultOptions allocator;
    std::vector<std::string> input_names;
    std::vector<std::string> output_names;
#endif
    bool model_loaded = false;
};

// ── NMS (Non-Maximum Suppression) ──
float ComputeIoU(const Detection& a, const Detection& b) {
    const float inter_x1 = std::max(a.x1, b.x1);
    const float inter_y1 = std::max(a.y1, b.y1);
    const float inter_x2 = std::min(a.x2, b.x2);
    const float inter_y2 = std::min(a.y2, b.y2);
    const float inter_area = std::max(0.0f, inter_x2 - inter_x1) * std::max(0.0f, inter_y2 - inter_y1);
    const float area_a = (a.x2 - a.x1) * (a.y2 - a.y1);
    const float area_b = (b.x2 - b.x1) * (b.y2 - b.y1);
    return inter_area / (area_a + area_b - inter_area + 1e-6f);
}

std::vector<Detection> ApplyNms(std::vector<Detection>& detections, float nms_threshold) {
    std::sort(detections.begin(), detections.end(),
              [](const Detection& a, const Detection& b) { return a.score > b.score; });
    std::vector<bool> suppressed(detections.size(), false);
    std::vector<Detection> result;
    for (std::size_t i = 0; i < detections.size(); ++i) {
        if (suppressed[i]) continue;
        result.push_back(detections[i]);
        for (std::size_t j = i + 1; j < detections.size(); ++j) {
            if (!suppressed[j] && ComputeIoU(detections[i], detections[j]) > nms_threshold) {
                suppressed[j] = true;
            }
        }
    }
    return result;
}

// ── 预处理: 图像数据 → 归一化浮点张量 (1, 3, 640, 640) ──
std::vector<float> Preprocess(const uint8_t* data, int width, int height, int channels, int stride) {
    std::vector<float> tensor(1 * kInputChannels * kInputHeight * kInputWidth, 0.0f);

    // 计算 letterbox 缩放参数
    const float scale = std::min(
        static_cast<float>(kInputWidth) / static_cast<float>(width),
        static_cast<float>(kInputHeight) / static_cast<float>(height));
    const int new_w = static_cast<int>(width * scale);
    const int new_h = static_cast<int>(height * scale);
    const int offset_x = (kInputWidth - new_w) / 2;
    const int offset_y = (kInputHeight - new_h) / 2;

    // 简易双线性缩放 + letterbox 填充 + 归一化 + HWC→CHW
    for (int dst_y = 0; dst_y < new_h; ++dst_y) {
        for (int dst_x = 0; dst_x < new_w; ++dst_x) {
            const float src_x_f = static_cast<float>(dst_x) / scale;
            const float src_y_f = static_cast<float>(dst_y) / scale;
            const int src_x = std::min(static_cast<int>(src_x_f), width - 1);
            const int src_y = std::min(static_cast<int>(src_y_f), height - 1);

            const int pixel_y = offset_y + dst_y;
            const int pixel_x = offset_x + dst_x;
            if (pixel_y < 0 || pixel_y >= kInputHeight || pixel_x < 0 || pixel_x >= kInputWidth) continue;

            const uint8_t* pixel = data + src_y * stride + src_x * channels;
            for (int c = 0; c < std::min(channels, kInputChannels); ++c) {
                // RGB 通道: pixel[0]=R, pixel[1]=G, pixel[2]=B (或 BGR 需翻转)
                tensor[c * kInputHeight * kInputWidth + pixel_y * kInputWidth + pixel_x] =
                    static_cast<float>(pixel[c]) / 255.0f;
            }
        }
    }
    return tensor;
}

// ── 后处理: 解析 YOLOv8 输出张量 ──
// YOLOv8 输出形状: (1, 4+num_classes, num_anchors) 即 (1, 5, 8400) 对单类检测
std::vector<Detection> PostprocessYolov8(
    const float* output_data,
    const std::vector<int64_t>& output_shape,
    int original_width,
    int original_height,
    float score_threshold) {

    std::vector<Detection> detections;

    if (output_shape.size() < 3) return detections;

    const int64_t num_features = output_shape[1];  // 4 + num_classes
    const int64_t num_anchors = output_shape[2];    // 8400

    if (num_features < 5) return detections;

    // letterbox 逆映射参数
    const float scale = std::min(
        static_cast<float>(kInputWidth) / static_cast<float>(original_width),
        static_cast<float>(kInputHeight) / static_cast<float>(original_height));
    const float offset_x = (kInputWidth - original_width * scale) / 2.0f;
    const float offset_y = (kInputHeight - original_height * scale) / 2.0f;

    for (int64_t a = 0; a < num_anchors; ++a) {
        // YOLOv8 转置输出: output[feature_idx][anchor_idx]
        const float cx = output_data[0 * num_anchors + a];
        const float cy = output_data[1 * num_anchors + a];
        const float w  = output_data[2 * num_anchors + a];
        const float h  = output_data[3 * num_anchors + a];

        // 找最大类别分数
        float max_class_score = 0.0f;
        int best_class_id = 0;
        for (int64_t c = 4; c < num_features; ++c) {
            const float class_score = output_data[c * num_anchors + a];
            if (class_score > max_class_score) {
                max_class_score = class_score;
                best_class_id = static_cast<int>(c - 4);
            }
        }

        if (max_class_score < score_threshold) continue;

        // 从 letterbox 坐标映射回原图
        float x1 = (cx - w / 2.0f - offset_x) / scale;
        float y1 = (cy - h / 2.0f - offset_y) / scale;
        float x2 = (cx + w / 2.0f - offset_x) / scale;
        float y2 = (cy + h / 2.0f - offset_y) / scale;

        // 边界裁剪
        x1 = std::max(0.0f, std::min(x1, static_cast<float>(original_width)));
        y1 = std::max(0.0f, std::min(y1, static_cast<float>(original_height)));
        x2 = std::max(0.0f, std::min(x2, static_cast<float>(original_width)));
        y2 = std::max(0.0f, std::min(y2, static_cast<float>(original_height)));

        if (x2 - x1 < 1.0f || y2 - y1 < 1.0f) continue;

        detections.push_back({x1, y1, x2, y2, max_class_score, best_class_id});
    }
    return detections;
}

// ── JSON 序列化 ──
std::string SerializeDetections(const std::vector<Detection>& detections) {
    std::ostringstream oss;
    oss << "{\"objects\":[";
    for (std::size_t i = 0; i < detections.size(); ++i) {
        if (i > 0) oss << ",";
        oss << "{\"label\":\"face\","
            << "\"bbox\":[" << static_cast<int>(detections[i].x1)
            << "," << static_cast<int>(detections[i].y1)
            << "," << static_cast<int>(detections[i].x2)
            << "," << static_cast<int>(detections[i].y2) << "],"
            << "\"score\":" << detections[i].score << "}";
    }
    oss << "],\"object_count\":" << detections.size() << "}";
    return oss.str();
}

} // namespace

// ═══════════════════════════════════════════════════════
// ai_plugin_api.h ABI 导出实现
// ═══════════════════════════════════════════════════════

extern "C" {

AI_PLUGIN_EXPORT int ai_plugin_init(const AiPluginInitParams* params, AiPluginHandle* out_handle) {
    if (params == nullptr || out_handle == nullptr) {
        return -2;
    }
    auto* ctx = new (std::nothrow) FaceDetectContext();
    if (ctx == nullptr) {
        return -4;
    }
    ctx->model_dir = params->model_dir != nullptr ? params->model_dir : "";
    ctx->device = params->device;
    ctx->max_batch_size = params->max_batch_size > 0 ? params->max_batch_size : 1;

    // 从 extra_config 解析阈值参数
    if (params->extra_config != nullptr) {
        // 简易 JSON 解析（仅提取 score_threshold / nms_threshold）
        std::string cfg(params->extra_config);
        auto extract_float = [&cfg](const char* key, float default_val) -> float {
            auto pos = cfg.find(key);
            if (pos == std::string::npos) return default_val;
            pos = cfg.find(':', pos);
            if (pos == std::string::npos) return default_val;
            try { return std::stof(cfg.substr(pos + 1)); } catch (...) { return default_val; }
        };
        ctx->score_threshold = extract_float("score_threshold", kDefaultScoreThreshold);
        ctx->nms_threshold = extract_float("nms_threshold", kDefaultNmsThreshold);
    }

#ifdef ONNXRUNTIME_ENABLED
    try {
        Ort::SessionOptions session_options;
        session_options.SetIntraOpNumThreads(2);
        session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);

        if (ctx->device == AI_DEVICE_CUDA) {
            OrtCUDAProviderOptions cuda_options;
            cuda_options.device_id = 0;
            session_options.AppendExecutionProvider_CUDA(cuda_options);
        }

        // 模型路径: <model_dir>/face_detect.onnx
        std::string model_path = ctx->model_dir + "/face_detect.onnx";
        ctx->session = std::make_unique<Ort::Session>(ctx->env, model_path.c_str(), session_options);

        // 获取输入/输出名称
        const std::size_t num_inputs = ctx->session->GetInputCount();
        for (std::size_t i = 0; i < num_inputs; ++i) {
            auto name = ctx->session->GetInputNameAllocated(i, ctx->allocator);
            ctx->input_names.emplace_back(name.get());
        }
        const std::size_t num_outputs = ctx->session->GetOutputCount();
        for (std::size_t i = 0; i < num_outputs; ++i) {
            auto name = ctx->session->GetOutputNameAllocated(i, ctx->allocator);
            ctx->output_names.emplace_back(name.get());
        }
        ctx->model_loaded = true;
    } catch (const std::exception&) {
        delete ctx;
        return -4;
    }
#else
    // 仿真模式：不加载模型
    ctx->model_loaded = false;
#endif

    *out_handle = ctx;
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_destroy(AiPluginHandle handle) {
    if (handle == nullptr) {
        return -3;
    }
    delete static_cast<FaceDetectContext*>(handle);
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_infer(AiPluginHandle handle, const AiPluginInput* input, AiPluginOutput* output) {
    if (handle == nullptr || input == nullptr || output == nullptr) {
        return -2;
    }
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    const auto t_start = std::chrono::steady_clock::now();

#ifdef ONNXRUNTIME_ENABLED
    if (!ctx->model_loaded || !ctx->session) {
        output->result_code = -5;
        output->error_message = "模型未加载";
        return -5;
    }

    // 解析输入图像尺寸
    int img_width = 0, img_height = 0, img_channels = 0, img_stride = 0;
    const uint8_t* img_data = nullptr;

    if (input->images != nullptr && input->image_count > 0) {
        // 结构化图像输入
        img_data = input->images[0].data;
        img_width = input->images[0].width;
        img_height = input->images[0].height;
        img_channels = input->images[0].channels;
        img_stride = input->images[0].stride > 0 ? input->images[0].stride : img_width * img_channels;
    } else if (input->media_data != nullptr && input->media_size > 0) {
        // 原始媒体数据：此处需外部解码，插件只处理已解码的像素数据
        // 对于演示目的，尝试将 media_data 作为原始 RGB 像素处理
        // 实际部署中需要集成 stb_image / OpenCV 解码
        output->result_code = -6;
        output->error_message = "请通过 AiImage 传入已解码图像数据";
        return -6;
    } else {
        output->result_code = -2;
        output->error_message = "无有效输入数据";
        return -2;
    }

    if (img_data == nullptr || img_width <= 0 || img_height <= 0) {
        output->result_code = -2;
        output->error_message = "图像数据无效";
        return -2;
    }

    try {
        // 预处理
        auto tensor_data = Preprocess(img_data, img_width, img_height, img_channels, img_stride);
        const int64_t input_shape[] = {1, kInputChannels, kInputHeight, kInputWidth};
        auto memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        auto input_tensor = Ort::Value::CreateTensor<float>(
            memory_info, tensor_data.data(), tensor_data.size(), input_shape, 4);

        // 构建 C 字符串名称数组
        std::vector<const char*> input_name_ptrs, output_name_ptrs;
        for (const auto& n : ctx->input_names) input_name_ptrs.push_back(n.c_str());
        for (const auto& n : ctx->output_names) output_name_ptrs.push_back(n.c_str());

        // 推理
        auto output_tensors = ctx->session->Run(
            Ort::RunOptions{nullptr},
            input_name_ptrs.data(), &input_tensor, input_name_ptrs.size(),
            output_name_ptrs.data(), output_name_ptrs.size());

        // 后处理
        auto& out_tensor = output_tensors[0];
        auto type_info = out_tensor.GetTensorTypeAndShapeInfo();
        auto shape = type_info.GetShape();
        const float* out_data = out_tensor.GetTensorData<float>();

        auto detections = PostprocessYolov8(out_data, shape, img_width, img_height, ctx->score_threshold);
        detections = ApplyNms(detections, ctx->nms_threshold);

        // 序列化结果
        std::string result_json = SerializeDetections(detections);
        output->result_json = new char[result_json.size() + 1];
        std::memcpy(output->result_json, result_json.c_str(), result_json.size() + 1);
        output->result_code = 0;
        output->error_message = nullptr;
    } catch (const std::exception& e) {
        std::string error = std::string("推理异常: ") + e.what();
        output->result_json = nullptr;
        output->result_code = -3;
        // error_message 指向静态或长生命周期字符串
        output->error_message = "ONNX Runtime 推理执行异常";
        return -3;
    }
#else
    // 仿真模式
    std::string result = "{\"objects\":[{\"label\":\"face\",\"bbox\":[100,80,200,220],\"score\":0.95}],"
                         "\"object_count\":1,\"mode\":\"simulation\"}";
    output->result_json = new char[result.size() + 1];
    std::memcpy(output->result_json, result.c_str(), result.size() + 1);
    output->result_code = 0;
    output->error_message = nullptr;
#endif

    const auto t_end = std::chrono::steady_clock::now();
    output->infer_time_ms = std::chrono::duration<double, std::milli>(t_end - t_start).count();
    return 0;
}

AI_PLUGIN_EXPORT void ai_plugin_free_result(AiPluginOutput* output) {
    if (output != nullptr && output->result_json != nullptr) {
        delete[] output->result_json;
        output->result_json = nullptr;
    }
}

AI_PLUGIN_EXPORT int ai_plugin_reload(AiPluginHandle handle, const char* new_model_dir) {
    if (handle == nullptr) return -3;
    auto* ctx = static_cast<FaceDetectContext*>(handle);

#ifdef ONNXRUNTIME_ENABLED
    try {
        std::string dir = new_model_dir != nullptr ? new_model_dir : ctx->model_dir;
        Ort::SessionOptions session_options;
        session_options.SetIntraOpNumThreads(2);
        session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        if (ctx->device == AI_DEVICE_CUDA) {
            OrtCUDAProviderOptions cuda_options;
            cuda_options.device_id = 0;
            session_options.AppendExecutionProvider_CUDA(cuda_options);
        }
        std::string model_path = dir + "/face_detect.onnx";
        ctx->session = std::make_unique<Ort::Session>(ctx->env, model_path.c_str(), session_options);
        ctx->model_dir = dir;
        ctx->model_loaded = true;
        return 0;
    } catch (...) {
        return -4;
    }
#else
    (void)new_model_dir;
    return 0;
#endif
}

AI_PLUGIN_EXPORT int ai_plugin_get_info(AiPluginHandle handle, AiPluginInfo* info) {
    if (handle == nullptr || info == nullptr) return -2;
    info->capability_id = "face_detect";
    info->capability_name = "face_detect";
    info->version = "1.0.0";
    info->model_version = "v1_0_0";
    info->description = "YOLOv8n 人脸检测推理插件";
    info->api_version_major = 1;
    info->api_version_minor = 0;
    info->api_version_patch = 0;
    info->current_device = static_cast<FaceDetectContext*>(handle)->device;
    info->extra_info_json = "{}";
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_warmup(AiPluginHandle handle) {
    if (handle == nullptr) return -2;
#ifdef ONNXRUNTIME_ENABLED
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    if (!ctx->model_loaded || !ctx->session) return -5;

    // 使用零填充张量做一次空推理以预热
    try {
        std::vector<float> dummy(1 * kInputChannels * kInputHeight * kInputWidth, 0.0f);
        const int64_t shape[] = {1, kInputChannels, kInputHeight, kInputWidth};
        auto mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        auto tensor = Ort::Value::CreateTensor<float>(mem_info, dummy.data(), dummy.size(), shape, 4);

        std::vector<const char*> input_ptrs, output_ptrs;
        for (const auto& n : ctx->input_names) input_ptrs.push_back(n.c_str());
        for (const auto& n : ctx->output_names) output_ptrs.push_back(n.c_str());

        ctx->session->Run(Ort::RunOptions{nullptr},
                          input_ptrs.data(), &tensor, input_ptrs.size(),
                          output_ptrs.data(), output_ptrs.size());
        return 0;
    } catch (...) {
        return -5;
    }
#else
    return 0;
#endif
}

AI_PLUGIN_EXPORT int ai_plugin_health_check(AiPluginHandle handle) {
    if (handle == nullptr) return -2;
#ifdef ONNXRUNTIME_ENABLED
    auto* ctx = static_cast<FaceDetectContext*>(handle);
    return ctx->model_loaded ? 0 : -6;
#else
    return 0;
#endif
}

} // extern "C"
