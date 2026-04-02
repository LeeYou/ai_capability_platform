# 11 — 测试 Web 页面设计

## 11.1 设计目标

提供一个**内置的浏览器端测试界面**，方便客户验收和日常测试各种 AI 能力，无需编写代码或使用 Postman 等工具。

## 11.2 技术选型

| 项 | 选型 | 说明 |
|----|------|------|
| **框架** | React 18 | 成熟的前端框架 |
| **UI 库** | Ant Design 5.x | 企业级 UI 组件库 |
| **构建工具** | Vite | 快速构建，产物体积小 |
| **HTTP 客户端** | axios | 请求发送 |
| **图像展示** | canvas + 自定义绘制 | 结果可视化（画框/标注） |
| **部署方式** | 构建为静态文件，由主服务提供 | 无需额外 Web 服务器 |

构建产物放置在 `/app/web/` 目录，由 C++ HTTP 服务作为静态文件提供。

## 11.3 页面结构

```
┌──────────────────────────────────────────────────────────┐
│  顶部导航栏                                                │
│  [Logo] AI 能力测试平台    [平台状态:正常] [授权状态:有效] │
├──────────┬───────────────────────────────────────────────┤
│ 左侧     │  主内容区                                      │
│ 能力导航  │                                               │
│          │  ┌─────────────────────────────────────────┐  │
│ ◉ 人脸相关│  │  当前能力: 人脸检测                       │  │
│   检测   │  │                                         │  │
│   识别   │  │  ┌──────────────┐ ┌──────────────────┐  │  │
│   活体   │  │  │  上传/拍照区   │ │  结果展示区       │  │  │
│   属性   │  │  │              │ │                  │  │  │
│ ◉ 证件相关│  │  │  [拖拽上传]   │ │  [图像+标注]     │  │  │
│   身份证  │  │  │  [拍照]      │ │  [JSON 结果]     │  │  │
│   证件分类│  │  │  [示例图片]   │ │  [耗时统计]      │  │  │
│ ◉ OCR   │  │  │              │ │                  │  │  │
│   通用   │  │  └──────────────┘ └──────────────────┘  │  │
│   手写   │  │                                         │  │
│   发票   │  │  ┌─────────────────────────────────────┐│  │
│ ◉ 印章   │  │  │  参数配置面板                        ││  │
│ ◉ 安全   │  │  │  阈值: [====●===] 0.5              ││  │
│   翻拍   │  │  │  最大人脸数: [10]                   ││  │
│   换脸   │  │  │  返回关键点: [✓]                    ││  │
│          │  │  └─────────────────────────────────────┘│  │
├──────────┤  │                                         │  │
│ 系统管理  │  │  [开始检测]  [清空]  [下载结果]          │  │
│ 能力列表  │  └─────────────────────────────────────────┘  │
│ 授权状态  │                                               │
│ 系统指标  │  ┌─────────────────────────────────────────┐  │
│ 管理操作  │  │  历史记录 (最近 20 条)                    │  │
│          │  │  #1 face_detect 42ms 成功 [查看]         │  │
│          │  │  #2 face_recognize 65ms 成功 [查看]      │  │
│          │  └─────────────────────────────────────────┘  │
└──────────┴───────────────────────────────────────────────┘
```

## 11.4 页面功能清单

### 11.4.1 能力测试页面 (每个能力一个)

| 功能 | 说明 |
|------|------|
| **图像上传** | 支持拖拽上传、点击选择、粘贴剪贴板 |
| **视频上传** | 支持上传小视频文件用于视频类能力测试 |
| **相机拍照** | 调用浏览器摄像头 API（活体检测等场景） |
| **示例图片** | 每个能力预置 2-3 张测试图片 |
| **参数配置** | 能力特定参数的可视化配置（滑块/输入框/开关） |
| **结果可视化** | 在图像上绘制检测框、关键点、文字标注 |
| **JSON 结果** | 原始 JSON 响应展示（可折叠/格式化） |
| **耗时统计** | 显示总耗时、推理耗时、网络耗时 |
| **历史记录** | 保存最近 20 条测试记录，可回看 |

### 11.4.2 各能力测试交互特化

| 能力 | 特殊交互 |
|------|---------|
| **人脸检测** | 图像上画矩形框 + 关键点，标注置信度 |
| **人脸识别** | 双图上传区（图A vs 图B），显示相似度仪表盘 |
| **指令活体** | 相机实时预览 + 指令提示（"请眨眼"） |
| **静默活体** | 单图 + 活体/非活体判定动画 |
| **人脸属性** | 属性标签卡片展示（图标+文字） |
| **身份证检测** | 图像上画四边形框，标注正反面 |
| **证件分类** | 分类结果 + 置信度条形图（Top-K） |
| **通用 OCR** | 图像上画文字区域多边形 + 文字标注 |
| **印章检测** | 图像上画圆形/椭圆检测框 |
| **印章识别** | 显示识别的印章文字 |
| **翻拍检测** | 真/假判定 + 分数仪表盘 |
| **换脸检测** | 支持图片或视频测试，显示帧级/片段级结果 + 分数仪表盘 |
| **发票/营业执照/电费单** | 结构化字段表格展示 |
| **合同识别** | 段落列表 + 关键字段高亮 |
| **手写签字** | 检测区域框 + 识别文字 |

### 11.4.3 系统管理页面

| 页面 | 内容 |
|------|------|
| **能力列表** | 所有能力的状态一览表（名称、版本、状态、设备、实例池） |
| **授权状态** | 当前 License 详情（类型、到期时间、授权能力、机器绑定状态） |
| **系统指标** | 各能力的调用统计图表（QPS、延迟、错误率） |
| **管理操作** | Reload/Rollback 操作界面（选择能力→选择操作→确认→结果） |

## 11.5 前端路由设计

```
/                           → 首页 (重定向到人脸检测)
/test/face_detect           → 人脸检测测试
/test/face_recognize        → 人脸识别测试
/test/liveness_action       → 指令活体测试
/test/liveness_silent       → 静默活体测试
/test/face_attribute        → 人脸属性测试
/test/idcard_detect         → 身份证检测测试
/test/doc_classify          → 证件分类测试
/test/handwriting_recognize → 手写签字测试
/test/business_license_ocr  → 营业执照测试
/test/seal_detect           → 印章检测测试
/test/seal_recognize        → 印章识别测试
/test/invoice_ocr           → 发票识别测试
/test/electricity_bill_ocr  → 电费单据测试
/test/contract_ocr          → 合同识别测试
/test/recapture_detect      → 翻拍检测测试
/test/deepfake_detect       → 换脸检测测试
/test/general_ocr           → 通用OCR测试

/admin/capabilities         → 能力列表
/admin/license              → 授权状态
/admin/metrics              → 系统指标
/admin/operations           → 管理操作
```

## 11.6 核心 React 组件

```
src/
├── App.tsx                         ← 主应用
├── layouts/
│   └── MainLayout.tsx              ← 主布局 (导航+内容)
├── pages/
│   ├── test/
│   │   ├── TestPage.tsx            ← 通用测试页模板
│   │   ├── FaceDetectTest.tsx      ← 人脸检测 (继承模板+自定义可视化)
│   │   ├── FaceRecognizeTest.tsx   ← 人脸识别 (双图上传)
│   │   ├── LivenessActionTest.tsx  ← 指令活体 (相机+指令)
│   │   └── ...                     ← 其他能力
│   └── admin/
│       ├── CapabilityList.tsx
│       ├── LicenseStatus.tsx
│       ├── Metrics.tsx
│       └── Operations.tsx
├── components/
│   ├── ImageUploader.tsx           ← 图像上传组件
│   ├── VideoUploader.tsx           ← 视频上传组件
│   ├── CameraCapture.tsx           ← 相机拍照组件
│   ├── ResultCanvas.tsx            ← 结果可视化画布
│   ├── JsonViewer.tsx              ← JSON 格式化展示
│   ├── ParamPanel.tsx              ← 参数配置面板
│   ├── HistoryList.tsx             ← 历史记录列表
│   ├── ScoreGauge.tsx              ← 分数仪表盘
│   └── StatusBadge.tsx             ← 状态标签
├── services/
│   └── api.ts                      ← API 请求封装
├── hooks/
│   ├── useInfer.ts                 ← 推理请求 Hook
│   └── useCapabilities.ts          ← 能力列表 Hook
├── types/
│   └── index.ts                    ← 类型定义
└── utils/
    ├── imageUtils.ts               ← 图像处理工具
    └── drawUtils.ts                ← Canvas 绘制工具
```

## 11.7 通用测试页模板

```tsx
// TestPage.tsx — 通用测试页模板 (伪代码)

interface TestPageProps {
  capabilityId: string;
  title: string;
  description: string;
  multiImage?: boolean;           // 是否支持多图 (人脸识别)
  supportVideo?: boolean;         // 是否支持视频输入
  useCamera?: boolean;            // 是否显示相机按钮
  params?: ParamDefinition[];     // 可配置参数
  renderResult: (result: any, imageRef: HTMLCanvasElement) => void;  // 自定义结果渲染
}

function TestPage({ capabilityId, title, params, renderResult, ... }: TestPageProps) {
  // 状态
  const [images, setImages] = useState<File[]>([]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [paramValues, setParamValues] = useState({});
  
  // 推理调用
  const handleInfer = async () => {
    setLoading(true);
    const base64Images = await Promise.all(images.map(toBase64));
    const response = videoFile
      ? await api.inferVideo(capabilityId, await toBase64(videoFile), videoFile.type, paramValues)
      : await api.infer(capabilityId, base64Images, paramValues);
    setResult(response);
    setLoading(false);
    // 保存到历史记录
    addToHistory(capabilityId, response);
  };
  
  return (
    <Layout>
      <Header>{title}</Header>
      <Content>
        <Row gutter={16}>
          {/* 上传区 */}
          <Col span={10}>
            <ImageUploader 
              multiple={multiImage}
              onChange={setImages}
            />
            {supportVideo && <VideoUploader onChange={setVideoFile} />}
            {useCamera && <CameraCapture onCapture={addImage} />}
          </Col>
          
          {/* 结果区 */}
          <Col span={14}>
            <ResultCanvas ref={canvasRef} image={images[0]} />
            <JsonViewer data={result} />
            <Statistic title="耗时" value={result?.cost_ms} suffix="ms" />
          </Col>
        </Row>
        
        {/* 参数面板 */}
        <ParamPanel definitions={params} values={paramValues} onChange={setParamValues} />
        
        {/* 操作按钮 */}
        <Button type="primary" onClick={handleInfer} loading={loading}>开始检测</Button>
        <Button onClick={clear}>清空</Button>
        <Button onClick={downloadResult}>下载结果</Button>
      </Content>
      
      {/* 历史记录 */}
      <HistoryList capabilityId={capabilityId} />
    </Layout>
  );
}
```

## 11.8 API 请求封装

```typescript
// services/api.ts

import axios from 'axios';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

export const api = {
  // 推理
  async infer(capabilityId: string, images: string[], params?: object) {
    const { data } = await client.post(`/infer/${capabilityId}`, {
      images: images.map(img => ({ data: img, format: 'jpeg' })),
      params: params || {},
    });
    return data;
  },
  
  async inferVideo(capabilityId: string, videoBase64: string, mimeType: string, params?: object) {
    const format = mimeType.includes('mp4') ? 'mp4' : 'avi';
    const { data } = await client.post(`/infer/${capabilityId}`, {
      media: {
        type: 'video',
        data: videoBase64,
        format,
      },
      params: params || {},
    });
    return data;
  },
  
  // 健康检查
  async health() {
    const { data } = await client.get('/health');
    return data;
  },
  
  // 能力列表
  async capabilities() {
    const { data } = await client.get('/capabilities');
    return data;
  },
  
  // 授权状态
  async licenseStatus() {
    const { data } = await client.get('/license/status');
    return data;
  },
  
  // Reload
  async reload(capabilityId: string, type: 'model' | 'plugin' | 'all') {
    const { data } = await client.post('/admin/reload', {
      capability_id: capabilityId,
      type,
    });
    return data;
  },
  
  // Rollback
  async rollback(capabilityId: string) {
    const { data } = await client.post('/admin/rollback', {
      capability_id: capabilityId,
    });
    return data;
  },
  
  // 指标
  async metrics() {
    const { data } = await client.get('/admin/metrics');
    return data;
  },
};
```

## 11.9 Canvas 结果可视化工具

```typescript
// utils/drawUtils.ts

export function drawDetectionBoxes(
  ctx: CanvasRenderingContext2D,
  boxes: Array<{ x: number; y: number; width: number; height: number; confidence: number; label?: string }>,
  options?: { color?: string; lineWidth?: number }
) {
  const color = options?.color || '#00FF00';
  const lineWidth = options?.lineWidth || 2;
  
  boxes.forEach((box, i) => {
    // 画框
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.strokeRect(box.x, box.y, box.width, box.height);
    
    // 标签背景
    const label = box.label || `${(box.confidence * 100).toFixed(1)}%`;
    ctx.fillStyle = color;
    ctx.fillRect(box.x, box.y - 20, ctx.measureText(label).width + 8, 20);
    
    // 标签文字
    ctx.fillStyle = '#000';
    ctx.font = '14px Arial';
    ctx.fillText(label, box.x + 4, box.y - 5);
  });
}

export function drawLandmarks(
  ctx: CanvasRenderingContext2D,
  landmarks: Array<[number, number]>,
  options?: { color?: string; radius?: number }
) {
  const color = options?.color || '#FF0000';
  const radius = options?.radius || 3;
  
  landmarks.forEach(([x, y]) => {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  });
}

export function drawOcrRegions(
  ctx: CanvasRenderingContext2D,
  regions: Array<{ box: number[][]; text: string; confidence: number }>
) {
  regions.forEach(region => {
    // 画多边形
    ctx.beginPath();
    ctx.moveTo(region.box[0][0], region.box[0][1]);
    region.box.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.strokeStyle = '#00AAFF';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // 文字标注
    ctx.fillStyle = 'rgba(0,170,255,0.7)';
    ctx.font = '12px Arial';
    ctx.fillText(region.text, region.box[0][0], region.box[0][1] - 4);
  });
}
```

## 11.10 构建与集成

```bash
# 前端项目在 web/ 目录
cd web/

# 开发模式
npm run dev          # 启动开发服务器 (localhost:5173)
                     # 代理 /api/* 到后端 localhost:8080

# 生产构建
npm run build        # 输出到 web/dist/

# Docker 构建时自动集成
# Dockerfile 中: COPY web/dist/ /app/web/
# C++ HTTP 服务: server.set_mount_point("/", "/app/web");
```

Vite 代理配置:

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
});
```
