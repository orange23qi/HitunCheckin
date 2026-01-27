#!/bin/bash
# Hitun.io 自动签到 - launchd 定时任务配置脚本

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_NAME="io.hitun.checkin"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "🚀 Hitun.io 自动签到 - 定时任务配置"
echo "======================================"

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

# 创建 LaunchAgents 目录(如果不存在)
mkdir -p "$HOME/Library/LaunchAgents"

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
if [ ! -f "$PYTHON_PATH" ]; then
    echo "❌ 错误: 虚拟环境 Python 不存在"
    exit 1
fi

echo "📝 配置信息:"
echo "  - Python 路径: $PYTHON_PATH"
echo "  - 脚本路径: $SCRIPT_DIR/hitun_checkin.py"
echo "  - plist 文件: $PLIST_FILE"
echo ""

# 生成 plist 文件
cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${SCRIPT_DIR}/hitun_checkin.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/launchd.out.log</string>
    
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/launchd.err.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "✅ plist 文件已创建"

# 卸载旧的任务(如果存在)
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🔄 卸载旧的定时任务..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
fi

# 加载新任务
echo "📥 加载定时任务..."
launchctl load "$PLIST_FILE"

echo ""
echo "✅ 定时任务配置完成!"
echo ""
echo "📋 任务信息:"
echo "  - 任务名称: $PLIST_NAME"
echo "  - 执行时间: 每天 09:00"
echo "  - 日志目录: $SCRIPT_DIR/logs/"
echo ""
echo "🔧 常用命令:"
echo "  - 查看任务状态: launchctl list | grep hitun"
echo "  - 手动执行一次: launchctl start $PLIST_NAME"
echo "  - 卸载任务: launchctl unload $PLIST_FILE"
echo "  - 查看日志: tail -f $SCRIPT_DIR/logs/checkin.log"
echo ""
