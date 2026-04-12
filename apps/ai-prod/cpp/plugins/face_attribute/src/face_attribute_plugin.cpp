/**
 * face_attribute 人脸属性多任务推理插件实现
 *
 * 基于 MobileNetV3-Large ONNX 多任务模型实现人脸属性分析，
 * 遵循 ai_plugin_api.h C ABI。
 *
 * 多任务输出头:
 *   - glasses   (binary,     2 classes)
 *   - mask      (binary,     2 classes)
 *   - hat       (binary,     2 classes)
 *   - integrity (binary,     2 classes)
 *   - side_face (binary,     2 classes)
 *   - expression(multiclass, 4 classes: neutral/smile/sad/angry)
 *   - head_pose (multiclass, 5 classes: front/left/right/up/down)
 *   - age       (regression, 1 output)
 *
 * 推理流程:
 *   1. ai_plugin_init: 加载 ONNX 模型到 ORT Session
 *   2. ai_plugin_infer: 预处理 → 推理 → 多头输出解析 → JSON 输出
 *   3. ai_plugin_destroy: 释放资源
 */

#include "face_attribute_plugin.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <new>
#include <sstream>
#include <string>
#include <vector>

#ifdef ONNXRUNTIME_ENABLED
#include <onnxruntime_cxx_api.h>
#endif

namespace {

// ── MobileNetV3 输入常量 ──
constexpr int kInputWidth = 224;
constexpr int kInputHeight = 224;
constexpr int kInputChannels = 3;

// ImageNet 归一化参数
constexpr float kMean[3] = {0.485f, 0.456f, 0.406f};
constexpr float kStd[3]  = {0.229f, 0.224f, 0.225f};

// 任务输出标签
const char* kExpressionLabels[] = {"neutral", "smile", "sad", "angry"};
const char* kHeadPoseLabels[] = {"front", "left", "right", "up", "down"};
constexpr int kNumExpressionClasses = 4;
constexpr int kNumHeadPoseClasses = 5;

// 多任务输出名称（与训练时导出的 ONNX 输出名一致）
const char* kBinaryTaskNames[] = {"glasses", "mask", "hat", "integrity", "side_face"};
constexpr int kNumBinaryTasks = 5;

// ── 插件上下文 ──
struct FaceAttributeContext {
    std::string model_dir;
    AiDeviceType device = AI_DEVICE_CPU;
    int max_batch_size = 1;
#ifdef ONNXRUNTIME_ENABLED
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "face_attribute"};
    std::unique_ptr<Ort::Session> session;
    Ort::AllocatorWithDefaultOptions allocator;
    std::vector<std::string> input_names;
    std::vector<std::string> output_names;
#endif
    bool model_loaded = false;
};

// ── Softmax ──
std::vector<float> Softmax(const float* data, int count) {
    std::vector<float> result(count);
    float max_val = *std::max_element(data, data + count);
    float sum = 0.0f;
    for (int i = 0; i < count; ++i) {
        result[i] = std::exp(data[i] - max_val);
        sum += result[i];
    }
    for (int i = 0; i < count; ++i) {
        result[i] /= (sum + 1e-8f);
    }
    return result;
}

int ArgMax(const std::vector<float>& v) {
    return static_cast<int>(std::max_element(v.begin(), v.end()) - v.begin());
}

// ── 预处理: 图像数据 → 归一化浮点张量 (1, 3, 224, 224) ──
std::vector<float> Preprocess(const uint8_t* data, int width, int height, int channels, int stride) {
    std::vector<float> tensor(1 * kInputChannels * kInputHeight * kInputWidth, 0.0f);

    for (int dst_y = 0; dst_y < kInputHeight; ++dst_y) {
        for (int dst_x = 0; dst_x < kInputWidth; ++dst_x) {
            // 简易最近邻缩放
            const int src_x = std::min(dst_x * width / kInputWidth, width - 1);
            const int src_y = std::min(dst_y * height / kInputHeight, height - 1);
            const uint8_t* pixel = data + src_y * stride + src_x * channels;

            for (int c = 0; c < std::min(channels, kInputChannels); ++c) {
                float val = static_cast<float>(pixel[c]) / 255.0f;
                val = (val - kMean[c]) / kStd[c];
                tensor[c * kInputHeight * kInputWidth + dst_y * kInputWidth + dst_x] = val;
            }
        }
    }
    return tensor;
}

// ── 转义 JSON 字符串 ──
std::string JsonString(const std::string& s) {
    return "\"" + s + "\"";
}

// ── 多任务输出解析 + JSON 序列化 ──
std::string SerializeMultiTaskOutputs(
    const std::vector<std::string>& output_names,
    const std::vector<std::vector<float>>& output_values) {

    std::ostringstream oss;
    oss << "{\"attributes\":{";

    bool first = true;
    for (std::size_t idx = 0; idx < output_names.size(); ++idx) {
        const auto& name = output_names[idx];
        const auto& values = output_values[idx];
        if (values.empty()) continue;

        if (!first) oss << ",";
        first = false;

        // 判断任务类型
        bool is_binary = false;
        for (int b = 0; b < kNumBinaryTasks; ++b) {
            if (name == kBinaryTaskNames[b]) { is_binary = true; break; }
        }

        if (is_binary && values.size() >= 2) {
            auto probs = Softmax(values.data(), static_cast<int>(values.size()));
            int pred = ArgMax(probs);
            oss << JsonString(name) << ":{"
                << "\"label\":" << (pred == 1 ? "\"yes\"" : "\"no\"")
                << ",\"class\":" << pred
                << ",\"confidence\":" << probs[pred] << "}";
        } else if (name == "expression" && values.size() >= kNumExpressionClasses) {
            auto probs = Softmax(values.data(), kNumExpressionClasses);
            int pred = ArgMax(probs);
            const char* label = pred < kNumExpressionClasses ? kExpressionLabels[pred] : "unknown";
            oss << JsonString(name) << ":{"
                << "\"label\":\"" << label << "\""
                << ",\"class\":" << pred
                << ",\"confidence\":" << probs[pred] << "}";
        } else if (name == "head_pose" && values.size() >= kNumHeadPoseClasses) {
            auto probs = Softmax(values.data(), kNumHeadPoseClasses);
            int pred = ArgMax(probs);
            const char* label = pred < kNumHeadPoseClasses ? kHeadPoseLabels[pred] : "unknown";
            oss << JsonString(name) << ":{"
                << "\"label\":\"" << label << "\""
                << ",\"class\":" << pred
                << ",\"confidence\":" << probs[pred] << "}";
        } else if (name == "age" && !values.empty()) {
            float age = std::max(0.0f, std::min(120.0f, values[0]));
            oss << JsonString(name) << ":{\"value\":" << age << "}";
        } else {
            // 未知输出头：原样输出第一个值
            oss << JsonString(name) << ":{\"raw\":" << (values.empty() ? 0.0f : values[0]) << "}";
        }
    }

    oss << "}}";
    return oss.str();
}

} // namespace

// ═══════════════════════════════════════════════════════
// ai_plugin_api.h ABI 导出实现
// ═══════════════════════════════════════════════════════

extern "C" {

AI_PLUGIN_EXPORT int ai_plugin_init(const AiPluginInitParams* params, AiPluginHandle* out_handle) {
    if (params == nullptr || out_handle == nullptr) return -2;

    auto* ctx = new (std::nothrow) FaceAttributeContext();
    if (ctx == nullptr) return -4;

    ctx->model_dir = params->model_dir != nullptr ? params->model_dir : "";
    ctx->device = params->device;
    ctx->max_batch_size = params->max_batch_size > 0 ? params->max_batch_size : 1;

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

        // 模型路径: <model_dir>/face_attribute.onnx
        std::string model_path = ctx->model_dir + "/face_attribute.onnx";
        ctx->session = std::make_unique<Ort::Session>(ctx->env, model_path.c_str(), session_options);

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
    ctx->model_loaded = false;
#endif

    *out_handle = ctx;
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_destroy(AiPluginHandle handle) {
    if (handle == nullptr) return -3;
    delete static_cast<FaceAttributeContext*>(handle);
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_infer(AiPluginHandle handle, const AiPluginInput* input, AiPluginOutput* output) {
    if (handle == nullptr || input == nullptr || output == nullptr) return -2;

    auto* ctx = static_cast<FaceAttributeContext*>(handle);
    const auto t_start = std::chrono::steady_clock::now();

#ifdef ONNXRUNTIME_ENABLED
    if (!ctx->model_loaded || !ctx->session) {
        output->result_code = -5;
        output->error_message = "模型未加载";
        return -5;
    }

    // 解析输入
    int img_width = 0, img_height = 0, img_channels = 0, img_stride = 0;
    const uint8_t* img_data = nullptr;

    if (input->images != nullptr && input->image_count > 0) {
        img_data = input->images[0].data;
        img_width = input->images[0].width;
        img_height = input->images[0].height;
        img_channels = input->images[0].channels;
        img_stride = input->images[0].stride > 0 ? input->images[0].stride : img_width * img_channels;
    } else if (input->media_data != nullptr && input->media_size > 0) {
        output->result_code = -6;
        output->error_message = "请通过 AiImage 传入已解码人脸裁剪图像";
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
        // 预处理: ImageNet 归一化 + resize 224×224
        auto tensor_data = Preprocess(img_data, img_width, img_height, img_channels, img_stride);
        const int64_t input_shape[] = {1, kInputChannels, kInputHeight, kInputWidth};
        auto memory_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        auto input_tensor = Ort::Value::CreateTensor<float>(
            memory_info, tensor_data.data(), tensor_data.size(), input_shape, 4);

        std::vector<const char*> input_name_ptrs, output_name_ptrs;
        for (const auto& n : ctx->input_names) input_name_ptrs.push_back(n.c_str());
        for (const auto& n : ctx->output_names) output_name_ptrs.push_back(n.c_str());

        // 推理
        auto output_tensors = ctx->session->Run(
            Ort::RunOptions{nullptr},
            input_name_ptrs.data(), &input_tensor, input_name_ptrs.size(),
            output_name_ptrs.data(), output_name_ptrs.size());

        // 解析多头输出
        std::vector<std::string> out_names;
        std::vector<std::vector<float>> out_values;
        for (std::size_t i = 0; i < output_tensors.size(); ++i) {
            auto& tensor = output_tensors[i];
            auto info = tensor.GetTensorTypeAndShapeInfo();
            auto shape = info.GetShape();
            const float* data = tensor.GetTensorData<float>();

            // 计算元素总数（跳过 batch 维度）
            int64_t element_count = 1;
            for (std::size_t d = 1; d < shape.size(); ++d) {
                element_count *= shape[d];
            }
            if (shape.size() == 1) {
                element_count = shape[0];
            }

            std::vector<float> values(data, data + element_count);
            out_names.push_back(ctx->output_names[i]);
            out_values.push_back(std::move(values));
        }

        // 序列化
        std::string result_json = SerializeMultiTaskOutputs(out_names, out_values);
        output->result_json = new char[result_json.size() + 1];
        std::memcpy(output->result_json, result_json.c_str(), result_json.size() + 1);
        output->result_code = 0;
        output->error_message = nullptr;

    } catch (const std::exception&) {
        output->result_json = nullptr;
        output->result_code = -3;
        output->error_message = "ONNX Runtime 推理执行异常";
        return -3;
    }
#else
    // 仿真模式
    std::string result =
        "{\"attributes\":{"
        "\"glasses\":{\"label\":\"no\",\"class\":0,\"confidence\":0.92},"
        "\"mask\":{\"label\":\"no\",\"class\":0,\"confidence\":0.88},"
        "\"hat\":{\"label\":\"no\",\"class\":0,\"confidence\":0.95},"
        "\"integrity\":{\"label\":\"yes\",\"class\":1,\"confidence\":0.91},"
        "\"side_face\":{\"label\":\"no\",\"class\":0,\"confidence\":0.87},"
        "\"expression\":{\"label\":\"neutral\",\"class\":0,\"confidence\":0.82},"
        "\"head_pose\":{\"label\":\"front\",\"class\":0,\"confidence\":0.93},"
        "\"age\":{\"value\":28.5}"
        "},\"mode\":\"simulation\"}";
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
    auto* ctx = static_cast<FaceAttributeContext*>(handle);

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
        std::string model_path = dir + "/face_attribute.onnx";
        ctx->session = std::make_unique<Ort::Session>(ctx->env, model_path.c_str(), session_options);
        ctx->model_dir = dir;
        ctx->model_loaded = true;

        // 更新输出名
        ctx->output_names.clear();
        const std::size_t num_outputs = ctx->session->GetOutputCount();
        for (std::size_t i = 0; i < num_outputs; ++i) {
            auto name = ctx->session->GetOutputNameAllocated(i, ctx->allocator);
            ctx->output_names.emplace_back(name.get());
        }
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
    info->capability_id = "face_attribute";
    info->capability_name = "face_attribute";
    info->version = "1.0.0";
    info->model_version = "v1_0_0";
    info->description = "MobileNetV3-Large 人脸属性多任务推理插件";
    info->api_version_major = 1;
    info->api_version_minor = 0;
    info->api_version_patch = 0;
    info->current_device = static_cast<FaceAttributeContext*>(handle)->device;
    info->extra_info_json = "{\"tasks\":[\"glasses\",\"mask\",\"hat\",\"integrity\",\"side_face\",\"expression\",\"head_pose\",\"age\"]}";
    return 0;
}

AI_PLUGIN_EXPORT int ai_plugin_warmup(AiPluginHandle handle) {
    if (handle == nullptr) return -2;
#ifdef ONNXRUNTIME_ENABLED
    auto* ctx = static_cast<FaceAttributeContext*>(handle);
    if (!ctx->model_loaded || !ctx->session) return -5;

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
    auto* ctx = static_cast<FaceAttributeContext*>(handle);
    return ctx->model_loaded ? 0 : -6;
#else
    return 0;
#endif
}

} // extern "C"
