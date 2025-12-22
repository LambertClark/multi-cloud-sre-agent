#!/bin/bash
# 多云SRE Agent启动脚本（Linux/Mac）
# 禁用代理以避免SOCKS连接问题

echo "============================================================"
echo "多云SRE Agent 启动脚本"
echo "============================================================"
echo ""

# 临时禁用代理环境变量
unset HTTP_PROXY
unset HTTPS_PROXY
unset ALL_PROXY
unset http_proxy
unset https_proxy
unset all_proxy

# 使用uv运行
echo "使用uv运行Python..."
echo ""

# 根据参数运行不同模式
if [ -z "$1" ]; then
    echo "运行模式: 交互模式"
    uv run python main.py --mode interactive
elif [ "$1" = "health" ]; then
    echo "运行模式: 健康检查"
    uv run python main.py --mode health
elif [ "$1" = "query" ]; then
    echo "运行模式: 查询"
    uv run python main.py --mode query --query "$2"
else
    echo "运行模式: 自定义"
    uv run python main.py "$@"
fi

echo ""
echo "============================================================"
echo "程序已退出"
echo "============================================================"
