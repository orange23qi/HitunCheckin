#!/bin/bash
set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 检查配置文件
if [ ! -f /app/data/config.json ]; then
    error "配置文件不存在: /app/data/config.json"
    error "请挂载配置文件到 /app/data/config.json"
    exit 1
fi

# 创建软链接到工作目录
ln -sf /app/data/config.json /app/config.json

# 启动 Xvfb (如果安装了)
if command -v Xvfb &> /dev/null; then
    log "启动 Xvfb..."
    Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    # 等待 Xvfb 启动
    sleep 2
fi

# 获取运行模式
RUN_MODE=${RUN_MODE:-"once"}
CRON_SCHEDULE=${CRON_SCHEDULE:-"0 8 * * *"}

log "=========================================="
log "Hitun.io 自动签到 Docker 容器"
log "运行模式: ${RUN_MODE}"
if [ "$RUN_MODE" = "cron" ]; then
    log "定时任务: ${CRON_SCHEDULE}"
fi
log "=========================================="

# 从 cron 表达式解析目标时和分 (仅支持固定时间，如 "30 8 * * *")
parse_schedule() {
    CRON_MIN=$(echo "$CRON_SCHEDULE" | awk '{print $1}')
    CRON_HOUR=$(echo "$CRON_SCHEDULE" | awk '{print $2}')

    # 验证是否为固定数字
    if ! echo "$CRON_MIN" | grep -qE '^[0-9]+$' || ! echo "$CRON_HOUR" | grep -qE '^[0-9]+$'; then
        error "Shell 调度器仅支持固定时间的 cron 表达式 (如 '30 8 * * *')"
        error "当前表达式: ${CRON_SCHEDULE}"
        exit 1
    fi

    log "调度目标时间: 每天 ${CRON_HOUR}:$(printf '%02d' ${CRON_MIN})"
}

# 计算距离下次执行还需要睡眠多少秒
calc_sleep_seconds() {
    local now_epoch=$(date +%s)
    # 构造今天的目标时间
    local target=$(date -d "today ${CRON_HOUR}:$(printf '%02d' ${CRON_MIN}):00" +%s 2>/dev/null)

    # 如果目标时间已过，则设为明天
    if [ "$target" -le "$now_epoch" ]; then
        target=$(( target + 86400 ))
    fi

    echo $(( target - now_epoch ))
}

run_checkin() {
    log "开始执行签到任务..."
    cd /app && python hitun_checkin.py --config /app/data/config.json || warn "签到任务执行失败"
}

case "$RUN_MODE" in
    "once")
        # 单次运行模式
        log "执行单次签到任务..."
        cd /app && python hitun_checkin.py --config /app/data/config.json
        ;;

    "cron")
        parse_schedule

        # 先执行一次签到（可选）
        if [ "${RUN_ON_START:-false}" = "true" ]; then
            log "启动时执行一次签到..."
            run_checkin
        fi

        # 使用 sleep 循环代替 cron 守护进程（在 Docker slim 镜像中更可靠）
        log "进入调度循环，等待定时任务执行..."
        while true; do
            sleep_secs=$(calc_sleep_seconds)
            next_time=$(date -d "@$(( $(date +%s) + sleep_secs ))" '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
            log "下次执行时间: ${next_time} (${sleep_secs} 秒后)"

            sleep "${sleep_secs}"

            log "定时任务触发"
            run_checkin
        done
        ;;

    "test")
        # 测试模式 - 仅测试登录
        log "执行登录测试..."
        cd /app && python hitun_checkin.py --config /app/data/config.json --test-login
        ;;

    *)
        error "未知运行模式: ${RUN_MODE}"
        error "支持的模式: once, cron, test"
        exit 1
        ;;
esac
