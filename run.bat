@echo off
REM 多云SRE Agent启动脚本（Windows）
REM 禁用代理以避免SOCKS连接问题

echo ============================================================
echo 多云SRE Agent 启动脚本
echo ============================================================
echo.

REM 临时禁用代理环境变量
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=
set http_proxy=
set https_proxy=
set all_proxy=

REM 设置Python路径（使用uv）
echo 使用uv运行Python...
echo.

REM 根据参数运行不同模式
if "%1"=="" (
    echo 运行模式: 交互模式
    uv run python main.py --mode interactive
) else if "%1"=="health" (
    echo 运行模式: 健康检查
    uv run python main.py --mode health
) else if "%1"=="query" (
    echo 运行模式: 查询
    uv run python main.py --mode query --query "%~2"
) else (
    echo 运行模式: 自定义
    uv run python main.py %*
)

echo.
echo ============================================================
echo 程序已退出
echo ============================================================
pause
