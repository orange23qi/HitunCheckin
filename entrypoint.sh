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

case "$RUN_MODE" in
    "once")
        # 单次运行模式
        log "执行单次签到任务..."
        cd /app && python hitun_checkin.py --config /app/data/config.json
        ;;

    "cron")
        # 定时任务模式
        log "设置定时任务..."

        # 创建 cron 任务文件
        echo "${CRON_SCHEDULE} cd /app && /usr/local/bin/python hitun_checkin.py --config /app/data/config.json >> /app/logs/cron.log 2>&1" > /etc/cron.d/hitun-checkin
        chmod 0644 /etc/cron.d/hitun-checkin
        crontab /etc/cron.d/hitun-checkin

        log "定时任务已设置: ${CRON_SCHEDULE}"
        log "容器将持续运行，等待定时任务执行..."

        # 先执行一次签到（可选）
        if [ "${RUN_ON_START:-false}" = "true" ]; then
            log "启动时执行一次签到..."
            cd /app && python hitun_checkin.py --config /app/data/config.json || warn "启动签到失败，但容器将继续运行"
        fi

        # 启动 cron 并保持前台运行
        cron -f
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
