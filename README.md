# OpenAI Prism 满血高推理反代服务 (OpenAI-Compatible Reverse Proxy)

本项目将 OpenAI 内部科研产品 **Prism** (`prism.openai.com`) 逆向转译为**标准 OpenAI `/v1/chat/completions` API**。

> **核心特性**：
> - ⚡️ **高思考不降智**：直通底层 `astra xhigh` / `o1/o3` 高思考深度模型，思考链 (`reasoning_content`) 完整流式透传。
> - 🛡 **独立额度池**：使用 Prism 独立配额，不占用常规网页版 ChatGPT 与主流 Codex 的日常额度。
> - 🌊 **完整流式传输**：Nginx 原生支持 Server-Sent Events (SSE)，关闭缓冲，实现毫秒级打字机逐字输出。
> - 🚀 **一键容器化部署**：专为首尔/海外轻量 VPS（Ubuntu/Debian）量身定制，Docker Compose 一键拉起。

---

## 一、 首尔服务器极速部署指南

### 1. 将打包好的代码上传到首尔服务器
在您的本地 Mac 终端中运行（替换 `YOUR_SERVER_IP` 为您的首尔服务器 IP）：
```bash
# 压缩打包
tar -czvf prism-proxy.tar.gz prism-proxy/

# 上传至首尔服务器
scp prism-proxy.tar.gz root@YOUR_SERVER_IP:/root/
```

### 2. 登录首尔服务器解压并一键部署
```bash
ssh root@YOUR_SERVER_IP

# 解压并进入目录
tar -xzvf prism-proxy.tar.gz
cd prism-proxy

# 执行一键部署脚本
bash deploy.sh
```
> `deploy.sh` 会自动安装 Docker、Docker Compose、配置防火墙放行 80/443 端口，并自动构建启动容器。

---

## 二、 如何获取 Prism 凭证 (Token / Cookie)

Prism 要求账号具有 **ChatGPT Plus** 或 **ChatGPT Pro** 订阅。获取步骤极简：

1. 在电脑浏览器（Chrome / Edge 等）打开并登录：**[https://prism.openai.com](https://prism.openai.com)**
2. 按键盘 **F12**（或右键 -> 检查）打开**开发者工具**，切换到 **网络 (Network)** 选项卡。
3. 在页面左侧点击新建或打开任意一个项目，或者在对话框中随意发一句话。
4. 在网络请求列表中，过滤筛选 `response_with_tools_start` 或 `projects` 或 `user`：
   - 点击该请求，查看 **标头 (Headers) -> 请求标头 (Request Headers)**；
   - 找到 **`Authorization`** 项，复制 `Bearer ` 后面的超长 JWT 字符串（通常以 `eyJ...` 开头）；
   - （可选）复制下方 **`Cookie`** 完整字符串。
5. 在服务器的 `prism-proxy/.env` 文件中填入：
   ```bash
   nano .env
   ```
   ```ini
   PRISM_TOKEN=eyJhbGciOiJSUzI1NiIs...你的完整Token...
   ```
6. 重启服务生效：
   ```bash
   docker compose restart
   ```

---

## 三、 客户端接入配置

部署完成后，即可像使用常规 OpenAI API 一样接入各类工具：

### 1. NextChat (ChatGPT-Next-Web) / Cherry Studio
- **接口地址 (API Base URL)**: `http://YOUR_SERVER_IP/v1`
- **API Key**: 填入 `.env` 中配置的 `PROXY_API_KEY`（默认 `sk-prism-secret-2026`）
- **自定义模型**: 添加 `o1-astra-xhigh` 或 `o3-high`

### 2. Cursor
在 Cursor 设置 -> **Models** 中：
- 开启自定义 OpenAI 兼容 API：
  - **OpenAI Base URL**: `http://YOUR_SERVER_IP/v1`
  - **OpenAI API Key**: `sk-prism-secret-2026`
- 添加模型名：`o1-astra-xhigh`

### 3. Python 官方 OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://YOUR_SERVER_IP/v1",
    api_key="sk-prism-secret-2026"
)

# 流式调用 (带思考链)
response = client.chat.completions.create(
    model="o1-astra-xhigh",
    messages=[
        {"role": "user", "content": "写一个快速排序算法并详细推导时间复杂度"}
    ],
    stream=True
)

for chunk in response:
    # 支持 DeepSeek / o1 思考链格式
    delta = chunk.choices[0].delta
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(f"[思考]: {delta.reasoning_content}", end="", flush=True)
    if delta.content:
        print(delta.content, end="", flush=True)
```

### 4. cURL 测试命令
```bash
curl http://YOUR_SERVER_IP/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-prism-secret-2026" \
  -d '{
    "model": "o1-astra-xhigh",
    "messages": [{"role": "user", "content": "你是谁？"}],
    "stream": true
  }'
```

---

## 四、 常见运维命令

```bash
# 查看服务实时运行日志
docker compose logs -f

# 重启反代服务
docker compose restart

# 更新修改 .env 配置后生效
docker compose up -d

# 停止服务
docker compose down
```
