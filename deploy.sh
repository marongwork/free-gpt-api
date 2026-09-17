#!/usr/bin/env bash
# ==============================================================================
# OpenAI Prism 反代服务首尔服务器一键部署脚本
# 适用系统: Ubuntu 20.04/22.04/24.04, Debian 11/12, CentOS 7/8/9
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}      OpenAI Prism 满血高推理反代一键部署程序         ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[提示] 当前非 root 用户，尝试获取 sudo 权限...${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# 2. 检查并安装 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}[1/5] 未检测到 Docker，正在自动安装 Docker 环境...${NC}"
    curl -fsSL https://get.docker.com | $SUDO sh
    $SUDO systemctl enable --now docker
    echo -e "${GREEN}[✓] Docker 安装完成!${NC}"
else
    echo -e "${GREEN}[1/5] Docker 已安装: $(docker --version)${NC}"
fi

# 3. 检查 Docker Compose
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${YELLOW}[2/5] 正在安装 Docker Compose 插件...${NC}"
    $SUDO apt-get update && $SUDO apt-get install -y docker-compose-plugin || true
    DOCKER_COMPOSE="docker compose"
fi
echo -e "${GREEN}[2/5] Docker Compose 已就绪!${NC}"

# 4. 检查环境配置文件
echo -e "${BLUE}[3/5] 检查环境配置 .env...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}[!] 已为您根据 .env.example 生成 .env 文件${NC}"
    else
        echo -e "${RED}[错误] 找不到 .env 或 .env.example，请检查文件完整性。${NC}"
        exit 1
    fi
fi

# 检查是否配置了 Token
if grep -q "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Im" .env; then
    echo -e "${YELLOW}------------------------------------------------------------${NC}"
    echo -e "${YELLOW}[注意] 当前 .env 中的 PRISM_TOKEN 仍为示例值！${NC}"
    echo -e "${YELLOW}请在部署完成后，使用 nano .env 或 vim .env 填入您的 Plus/Pro Token${NC}"
    echo -e "${YELLOW}然后执行: docker compose restart 重启生效。${NC}"
    echo -e "${YELLOW}------------------------------------------------------------${NC}"
fi

# 5. 防火墙配置开放 80 / 443 端口
if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
    echo -e "${BLUE}[4/5] 检测到 UFW 防火墙，正在放行 80 与 443 端口...${NC}"
    $SUDO ufw allow 80/tcp
    $SUDO ufw allow 443/tcp
    echo -e "${GREEN}[✓] 端口已放行!${NC}"
else
    echo -e "${GREEN}[4/5] 防火墙检测通过。${NC}"
fi

# 6. 构建并拉起容器
echo -e "${BLUE}[5/5] 正在构建并拉起 Prism 反代容器...${NC}"
$DOCKER_COMPOSE down --remove-orphans 2>/dev/null || true
$DOCKER_COMPOSE up -d --build

# 等待服务初始化
echo -e "${BLUE}正在等待服务自检 (约 3 秒)...${NC}"
sleep 3

# 健康检查
HEALTH_CHECK=$(curl -s http://127.0.0.1/health || curl -s http://127.0.0.1:8000/health || echo "FAIL")

if echo "$HEALTH_CHECK" | grep -q "online"; then
    SERVER_IP=$(curl -s https://api.ipify.org || echo "您的首尔服务器IP")
    PROXY_KEY=$(grep "PROXY_API_KEY=" .env | cut -d '=' -f2)
    echo -e ""
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}             🎉 Prism 反代服务部署成功！              ${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo -e "接口地址 (Base URL): ${BLUE}http://${SERVER_IP}/v1${NC}"
    echo -e "防盗刷密钥 (API Key): ${YELLOW}${PROXY_KEY}${NC}"
    echo -e "支持模型: ${GREEN}o1-astra-xhigh, o3-high, gpt-5.2-prism${NC}"
    echo -e ""
    echo -e "测试命令示例 (在终端直接执行):"
    echo -e "${BLUE}curl http://127.0.0.1/v1/chat/completions \\"
    echo -e "  -H \"Content-Type: application/json\" \\"
    echo -e "  -H \"Authorization: Bearer ${PROXY_KEY}\" \\"
    echo -e "  -d '{\"model\": \"o1-astra-xhigh\", \"messages\": [{\"role\": \"user\", \"content\": \"你好，请用一句话介绍你自己\"}], \"stream\": false}'${NC}"
    echo -e "======================================================"
else
    echo -e "${RED}[!] 服务启动可能异常，请检查日志: docker compose logs -f${NC}"
fi
