# ⚡️ Free-GPT-API · 零计费无限 GPT Token！满血 o1 / o3 高推理反代服务

> **零 API 计费账单 · 无限 GPT Token 配额 · 直通 o1 / o3 满血深度思考 · 四档思考强度自由调节**
>
> 将 OpenAI 内部科研平台 **Prism** 逆向转译为**标准 OpenAI `/v1/chat/completions` API**，让任意客户端即刻畅享不计费、无降智的高推理体验！

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-green.svg)](https://platform.openai.com/)

---

## 🌟 核心亮点

- 💎 **无限 GPT Token 畅享**：基于 Prism 独立通道与专属额度池，**免除官方 API 昂贵的 Token 扣费**，告别月度账单焦虑，尽享高强度 AI 交互！
- 🧠 **满血高思考深度**：底层直连 `gpt-5.6-terra` 等高推理引擎，思考链 (`reasoning_content`) 完整原汁原味透传，绝不降智。
- 🎛️ **四档思考强度自由调节**：通过 `reasoning_effort` 参数在 `low` / `medium` / `high` / `xhigh` 四档自由切换，平衡速度与深度。
- 💬 **完整多轮上下文记忆**：内置智能上下文重构引擎，完美维持多轮对话历史，彻底告别单轮遗忘问题。
- 🌊 **毫秒级极速流式**：原生支持 Server-Sent Events (SSE)，Nginx 零缓冲全双工逐字打字机推流，体验丝滑流畅。
- 🔌 **全生态无缝兼容**：100% 遵循 OpenAI API 规范，无缝直接 **Cursor**、**NextChat**、**Cherry Studio**、**Chatbox**、**LibreChat**、**DSH (DeepSeek Harness)** 及官方 **Python/Node SDK**。
- 🚀 **极简一键部署**：支持任何 Linux VPS（Ubuntu / Debian / CentOS 等），一行命令即可通过 Docker 快速拉起。

---

## 📦 极速部署指南 (通用 VPS / 云服务器)

### 方式一：Git 克隆一键部署（推荐）

在你的任何 Linux 服务器上执行：

```bash
# 1. 克隆本仓库
git clone https://github.com/marongwork/free-gpt-api.git
cd free-gpt-api

# 2. 复制配置文件模板
cp .env.example .env

# 3. 填入你的 Prism 凭证（获取方法见下文）
nano .env

# 4. 执行一键安装与启动脚本
bash deploy.sh
```

> `deploy.sh` 会自动检测并安装 Docker、Docker Compose、开放防火墙对应端口并启动服务。

---

### 方式二：Docker Compose 标准部署

如果你已安装 Docker，也可直接使用 Compose 启动：

```bash
cd free-gpt-api
cp .env.example .env
# 编辑配置
vim .env

# 后台构建并启动
docker compose up -d --build
```

服务启动后，默认对外提供端口：
- **`80`** 端口（经由 Nginx 高性能反代与 SSE 优化）
- **`8000`** 端口（内部后端服务）

---

## 🔑 如何获取 Prism 凭证 (Token)

> **前提条件**：账号具备 **ChatGPT Plus** 或 **ChatGPT Pro** 订阅。

1. 在浏览器中打开并登录：**[https://prism.openai.com](https://prism.openai.com)**
2. 按键盘 **F12** 打开**开发者工具**，切换到 **网络 (Network)** 选项卡。
3. 在页面左侧点击新建项目或在对话框中随意发送一条测试消息。
4. 在网络请求列表中，过滤筛选 `response_with_tools_start` 或 `projects`：
   - 点击该请求，查看 **标头 (Headers) -> 请求标头 (Request Headers)**；
   - 找到 **`Authorization`** 项，复制 `Bearer ` 后面的完整 JWT 字符串（以 `eyJ...` 开头）；
   - （可选）复制下方 **`Cookie`** 完整字符串。
5. 将凭据粘贴进 `.env` 文件中：
   ```ini
   PRISM_TOKEN=eyJhbGciOiJSUzI1NiIs...你的完整Token...
   ```
6. 重启服务即刻生效：
   ```bash
   docker compose restart
   ```

---

## 🛠 客户端接入配置

部署成功后，你的服务 Base URL 即为：`http://你的服务器IP/v1`（如配置了域名及反代即为 `https://你的域名/v1`）。

### 1. Cursor
- 打开设置 -> **Models** -> 开启 **OpenAI API Key**
- **OpenAI Base URL**: `http://你的服务器IP/v1`
- **OpenAI API Key**: 填入你在 `.env` 中设置的 `PROXY_API_KEY`（默认 `sk-prism-secret-2026`）
- **Model Name**: 添加 `o1-astra-xhigh` 或 `01-astra-xhigh`

### 2. NextChat / Cherry Studio / Chatbox
- **接口地址 (API Base URL)**: `http://你的服务器IP/v1`
- **API Key**: `sk-prism-secret-2026`
- **自定义模型**: 添加 `o1-astra-xhigh`、`o3-high`、`gpt-4o`

### 3. Python 官方 SDK

基础调用：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://你的服务器IP/v1",
    api_key="sk-prism-secret-2026"
)

# 完整流式调用（含思考链）
response = client.chat.completions.create(
    model="o1-astra-xhigh",
    messages=[
        {"role": "user", "content": "请详细分析牛顿力学与相对论在极端条件下的数学推导差异"}
    ],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    # 思考链实时推流
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(f"[思考]: {delta.reasoning_content}", end="", flush=True)
    # 正文内容
    if delta.content:
        print(delta.content, end="", flush=True)
```

指定思考强度（`reasoning_effort`）：

```python
response = client.chat.completions.create(
    model="o1-astra-xhigh",
    messages=[{"role": "user", "content": "帮我写一个快速排序"}],
    extra_body={"reasoning_effort": "high"},  # low / medium / high / xhigh
    stream=True
)
```

### 4. cURL 测试

```bash
# 普通调用
curl http://你的服务器IP/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-prism-secret-2026" \
  -d '{
    "model": "o1-astra-xhigh",
    "messages": [
      {"role": "user", "content": "你好，请用一句话介绍你自己"}
    ],
    "stream": false
  }'

# 指定思考强度
curl http://你的服务器IP/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-prism-secret-2026" \
  -d '{
    "model": "o1-astra-xhigh",
    "reasoning_effort": "xhigh",
    "messages": [
      {"role": "user", "content": "证明黎曼假设"}
    ],
    "stream": true
  }'
```

### 5. DSH (DeepSeek Harness) Web UI

在 `~/.dsh/settings.yaml` 中添加 provider 配置：

```yaml
providers:
  - name: prism
    baseUrl: https://你的域名/v1
    apiKey: sk-prism-secret-2026
    models:
      - id: o1-astra-xhigh
        reasoningEfforts: [low, medium, high, xhigh]
      - id: 01-astra-xhigh
        reasoningEfforts: [low, medium, high, xhigh]
      - id: o1-high
        reasoningEfforts: [low, medium, high, xhigh]
      - id: o3-high
        reasoningEfforts: [low, medium, high, xhigh]
      - id: gpt-4o
```

配置完成后，DSH UI 将在推理模型旁显示思考强度调节滑块，可在 `low` → `xhigh` 之间实时切换。

---

## 📋 支持模型列表

| 客户端请求模型名 | 映射底层引擎 | 思考强度支持 | 特性说明 |
|---|---|---|---|
| `o1-astra-xhigh` | `gpt-5.6-terra` | ✅ low/medium/high/xhigh | **默认推荐**，满血极高推理深度，完整思考链 |
| `01-astra-xhigh` | `gpt-5.6-terra` | ✅ | 同上，数字前缀兼容别名 |
| `o1-high` | `gpt-5.6-terra` | ✅ | 高推理深度，兼顾逻辑与复杂推理 |
| `01-high` | `gpt-5.6-terra` | ✅ | 同上，数字前缀兼容别名 |
| `o3-high` | `gpt-5.6-terra` | ✅ | o3 架构深度思考模式 |
| `03-high` | `gpt-5.6-terra` | ✅ | 同上，数字前缀兼容别名 |
| `o1` | `gpt-5.6-terra` | ✅ | 标准 o1 入口 |
| `o1-preview` | `gpt-5.6-terra` | ✅ low | 预览档，默认 low effort |
| `gpt-5.2-prism` | `gpt-5.6-terra` | ❌ | 超长上下文综合生成模型 |
| `gpt-4o` | `gpt-4o` | ❌ | 极速日常对话与代码生成 |

> **注意**：模型名支持 `o` 和 `0`（数字零）前缀互换，例如 `o1-high` 和 `01-high` 等价。

---

## 常用运维命令

```bash
# 查看实时运行日志
docker compose logs -f

# 重启反代服务
docker compose restart

# 更新 .env 配置后应用
docker compose up -d

# 停止服务
docker compose down
```

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源发布。
