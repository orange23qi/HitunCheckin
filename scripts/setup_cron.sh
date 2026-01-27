#!/bin/bash
# Hitun.io 自动签到 - Cron 定时任务配置脚本

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Hitun.io 自动签到 - Cron 定时任务配置"
echo "=========================================="

# 检查 Python 脚本是否存在
if [ ! -f "$SCRIPT_DIR/hitun_checkin.py" ]; then
    echo "❌ 错误: 找不到 hitun_checkin.py"
    exit 1
fi

# 检查配置文件是否存在
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
    echo "❌ 错误: 找不到 config.json"
    echo "请先复制 config.json.example 为 config.json 并填入登录信息"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "❌ 错误: 找不到虚拟环境"
    echo "请先创建虚拟环境:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# 使用虚拟环境的 Python
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"

# Cron 任务配置 (每天早上 9:00 执行)
CRON_JOB="0 9 * * * cd $SCRIPT_DIR && $PYTHON_PATH hitun_checkin.py >> logs/cron.log 2>&1"

echo "📝 将添加以下 cron 任务:"
echo "  $CRON_JOB"
echo ""

# 检查是否已存在相同的任务
if crontab -l 2>/dev/null | grep -F "hitun_checkin.py" > /dev/null; then
    echo "⚠️  检测到已存在的 hitun 签到任务"
    read -p "是否要替换? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消"
        exit 1
    fi
    
    # 删除旧任务
    crontab -l 2>/dev/null | grep -v "hitun_checkin.py" | crontab -
    echo "🗑️  已删除旧任务"
fi

# 添加新任务
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Cron 定时任务配置完成!"
echo ""
echo "📋 任务信息:"
echo "  - 执行时间: 每天 09:00"
echo "  - 日志文件: $SCRIPT_DIR/logs/cron.log"
echo ""
echo "🔧 常用命令:"
echo "  - 查看所有 cron 任务: crontab -l"
echo "  - 编辑 cron 任务: crontab -e"
echo "  - 删除所有 cron 任务: crontab -r"
echo "  - 查看日志: tail -f $SCRIPT_DIR/logs/checkin.log"
echo ""
echo "💡 提示: 如果 cron 任务没有执行,请检查 macOS 的隐私设置"
echo "   系统偏好设置 > 安全性与隐私 > 完全磁盘访问权限 > 添加 cron"
echo ""
