#ifndef FACE_ATTRIBUTE_PLUGIN_H
#define FACE_ATTRIBUTE_PLUGIN_H

/**
 * face_attribute 人脸属性多任务推理插件
 *
 * 模型: MobileNetV3-Large 多任务头（ONNX 格式）
 * 输入: 已裁剪的人脸图像（224×224 RGB）
 * 输出: JSON 格式多任务属性结果
 *       - 二分类: glasses, mask, hat, integrity, side_face
 *       - 多分类: expression(4类), head_pose(5类)
 *       - 回归:   age
 *
 * 实现 ai_plugin_api.h 定义的标准 C ABI，由 ai-prod C++ proxy
 * 通过 dlopen/LoadLibrary 动态加载。
 */

#include "ai_platform/ai_plugin_api.h"

#endif
