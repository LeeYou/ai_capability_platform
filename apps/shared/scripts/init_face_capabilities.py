"""人脸检测与属性分析能力初始化脚本。

通过 ai-train REST API 注册 face_detect 和 face_attribute 两个能力，
并绑定对应的数据集目录。运行本脚本前需确保 ai-train 服务已启动。

使用方式：
  python init_face_capabilities.py
  python init_face_capabilities.py --api-base http://localhost:26000
  python init_face_capabilities.py --datasets-root /data/ai_capability_platform/datasets
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error, request


DEFAULT_API_BASE = "http://localhost:26000"


def _post(url: str, payload: dict) -> dict:
    """发送 POST 请求。"""
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"  HTTP {exc.code}: {body}")
        return {"error": body}


def _get(url: str) -> dict:
    """发送 GET 请求。"""
    req = request.Request(url)
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def register_capability(api_base: str, capability_name: str, display_name: str, task_type: str) -> None:
    """注册能力。"""
    print(f"\n[1] 注册能力: {capability_name} ({task_type})")
    result = _post(f"{api_base}/api/v1/capabilities", {
        "capability_name": capability_name,
        "display_name": display_name,
        "task_type": task_type,
    })
    if "error" not in result:
        print(f"  ✓ 已注册: {result.get('capability_name', capability_name)}")
    else:
        print(f"  → 可能已存在，跳过")


def bind_dataset(api_base: str, capability_name: str, dataset_path: str) -> None:
    """绑定数据集。"""
    print(f"\n[2] 绑定数据集: {capability_name} → {dataset_path}")
    dataset_dir = Path(dataset_path)
    if not dataset_dir.exists():
        dataset_dir.mkdir(parents=True, exist_ok=True)
        print(f"  → 已创建数据集目录: {dataset_dir}")

    result = _post(f"{api_base}/api/v1/dataset-bindings", {
        "capability_name": capability_name,
        "dataset_path": dataset_path,
        "dataset_status": "ready",
    })
    if "error" not in result:
        print(f"  ✓ 已绑定: {result.get('dataset_path', dataset_path)}")
    else:
        print(f"  → 绑定可能已存在，跳过")


def verify_health(api_base: str) -> bool:
    """检查 ai-train 服务健康状态。"""
    try:
        result = _get(f"{api_base}/api/v1/health")
        print(f"[0] 服务状态: {result.get('status', 'unknown')}")
        return result.get("status") == "ok"
    except Exception as exc:
        print(f"[0] 服务不可达: {exc}")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="初始化人脸检测与属性分析能力")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="ai-train API 基地址")
    parser.add_argument("--datasets-root", default="/data/ai_capability_platform/datasets",
                        help="数据集根目录")
    args = parser.parse_args(argv)

    api_base = args.api_base.rstrip("/")
    datasets_root = Path(args.datasets_root)

    print("=" * 60)
    print("人脸检测与属性分析能力初始化")
    print("=" * 60)
    print(f"API 基地址: {api_base}")
    print(f"数据集根目录: {datasets_root}")

    if not verify_health(api_base):
        print("\n✗ ai-train 服务不可达，请先启动服务")
        return 1

    # ── face_detect: YOLOv8n 人脸检测 ──
    print("\n" + "─" * 40)
    print("能力 1: face_detect (YOLOv8n 人脸检测)")
    print("─" * 40)
    register_capability(api_base, "face_detect", "人脸检测", "detection")
    face_detect_dataset = str(datasets_root / "face_detect")
    bind_dataset(api_base, "face_detect", face_detect_dataset)

    # 创建数据集目录结构提示
    expected_dirs = [
        Path(face_detect_dataset) / "images" / "train",
        Path(face_detect_dataset) / "images" / "val",
        Path(face_detect_dataset) / "labels" / "train",
        Path(face_detect_dataset) / "labels" / "val",
    ]
    for d in expected_dirs:
        d.mkdir(parents=True, exist_ok=True)
    print(f"\n  数据集目录结构已创建:")
    print(f"    {face_detect_dataset}/")
    print(f"    ├── images/train/  (放置 WIDER FACE 训练图像)")
    print(f"    ├── images/val/    (放置 WIDER FACE 验证图像)")
    print(f"    ├── labels/train/  (放置 YOLO 格式标注文件)")
    print(f"    └── labels/val/    (放置 YOLO 格式标注文件)")

    # ── face_attribute: MobileNetV3-Large 多任务属性分析 ──
    print("\n" + "─" * 40)
    print("能力 2: face_attribute (MobileNetV3-Large 多任务属性)")
    print("─" * 40)
    register_capability(api_base, "face_attribute", "人脸属性分析", "classification")
    face_attr_dataset = str(datasets_root / "face_attribute")
    bind_dataset(api_base, "face_attribute", face_attr_dataset)

    # 创建数据集目录结构提示
    attr_dataset_dir = Path(face_attr_dataset)
    attr_dataset_dir.mkdir(parents=True, exist_ok=True)
    (attr_dataset_dir / "crops").mkdir(parents=True, exist_ok=True)
    print(f"\n  数据集目录结构已创建:")
    print(f"    {face_attr_dataset}/")
    print(f"    ├── train.csv   (训练集 CSV: image_path,glasses,mask,hat,...)")
    print(f"    ├── val.csv     (验证集 CSV)")
    print(f"    └── crops/      (人脸裁剪图像目录)")

    # ── 验证结果 ──
    print("\n" + "─" * 40)
    print("验证注册结果")
    print("─" * 40)
    caps = _get(f"{api_base}/api/v1/capabilities")
    for item in caps.get("items", []):
        if item.get("capability_name") in ("face_detect", "face_attribute"):
            print(f"  ✓ {item['capability_name']}: task_type={item['task_type']}, "
                  f"dataset_status={item['dataset_status']}")

    print("\n" + "=" * 60)
    print("初始化完成！")
    print("\n后续步骤：")
    print("  1. 将 WIDER FACE 数据转换为 YOLO 格式，放入 face_detect 数据集目录")
    print("  2. 准备人脸裁剪图像和 CSV 标签文件，放入 face_attribute 数据集目录")
    print("  3. 通过 API 创建训练任务并执行训练")
    print("  4. 训练完成后注册模型产物，进入测试和推理环节")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
