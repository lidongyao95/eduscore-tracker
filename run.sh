#!/bin/bash
# eduscore-tracker 启动脚本
set -e

PORT=${PORT:-5001}
MODE=${1:-formal}

echo "========================================"
echo "  EduScore Tracker 启动"
echo "========================================"

# 检查 Python 版本
python3 --version

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（清华镜像，无需翻墙）
echo "[2/4] 安装 Python 依赖..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet

if [ "$MODE" = "demo" ]; then
    echo "[3/4] 重建数据库并初始化演示数据..."
    python -m scripts.rebuild_db
    python -m scripts.demo_data
    echo ""
    echo "  📊 演示模式：1个教学班 · 5个单元 · 15名学生 · 平行前测后测"
    STUDENT_HINT="student1 / student123"
else
    echo "[3/4] 正式模式：仅确保数据库结构和默认教师账号。"
    python -m scripts.init_db
    STUDENT_HINT="请使用你自己的正式账号"
fi

# 启动服务
echo "[4/4] 启动服务..."
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  🚀 EduScore Tracker 运行中             ║"
printf "  ║  访问地址: http://localhost:%-11s║\n" "${PORT}"
if [ "$MODE" = "demo" ]; then
    echo "  ║  账号提示: teacher / teacher123         ║"
else
    echo "  ║  账号提示: 首次启动会自动创建 teacher     ║"
fi
printf "  ║  学生提示: %-28s║\n" "${STUDENT_HINT}"
echo "  ╚══════════════════════════════════════════╝"
echo ""
export PORT
python -m app.app
