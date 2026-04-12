#ifndef FACE_DETECT_PLUGIN_H
#define FACE_DETECT_PLUGIN_H

/**
 * face_detect 人脸检测推理插件
 *
 * 模型: YOLOv8n（ONNX 格式）
 * 输入: 图像数据（BGR / RGB）
 * 输出: JSON 格式检测结果，包含边界框、置信度
 *
 * 实现 ai_plugin_api.h 定义的标准 C ABI，由 ai-prod C++ proxy
 * 通过 dlopen/LoadLibrary 动态加载。
 */

#include "ai_platform/ai_plugin_api.h"

#endif
