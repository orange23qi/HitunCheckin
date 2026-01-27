# Hitun.io 自动签到工具

每天自动登录 [hitun.io](https://hitun.io) 并完成签到，获取流量奖励。支持 Docker 部署（群晖 NAS 友好）及手动 Cookie 注入以绕过 Cloudflare。

## ✨ 功能特性

- 🤖 **自动化程度高**：全自动登录、寻找签到按钮、获取流量统计。
- 🛡️ **绕过验证**：集成 `undetected-chromedriver`，支持**手动注入 Cookie** 彻底绕过 Cloudflare 挑战。
- 📦 **Docker 支持**：提供一键部署方案，完美适配群晖 NAS 及其他 Linux 服务器。
- ⏰ **灵活定时**：内置 Cron 支持，可自定义执行时间。
- 📢 **消息通知**：支持 Server 酱推送，签到结果实时知晓。
- 📝 **详细日志**：记录每一步操作，方便排查问题。

---

## 🚀 快速开始 (Docker 部署 - 推荐)

这是最稳定的部署方式，适合 24 小时运行的服务器或 NAS。

### 1. 准备工作
在项目目录下创建 `data` 文件夹，并参考模板创建配置文件：
```bash
mkdir -p data
cp config.json.example data/config.json
```
编辑 `data/config.json` 填入邮箱和密码。

### 2. 使用 Docker Compose 启动
```bash
# 启动项目 (会自动构建镜像)
docker-compose up -d

# 查看运行日志
docker logs -f hitun-checkin
```

### 3. 环境参数说明
在 `docker-compose.yml` 中可以调整以下环境变量：
- `RUN_MODE`: `cron` (定时模式) 或 `once` (运行一次后退出)
- `CRON_SCHEDULE`: 定时任务表达式 (默认 `0 8 * * *` 每天早上8点)
- `RUN_ON_START`: 容器启动时是否立即运行一次 (`true`/`false`)
- `TZ`: 时区 (默认 `Asia/Shanghai`)

---

## 🛡️ 绕过 Cloudflare (手动注入 Cookie)

如果程序自动运行因 Cloudflare 验证而失败，请使用此方法。

### 1. 获取 Cookie
在登录后的 `hitun.io` 页面，按 `F12` 打开控制台，执行以下脚本：
```javascript
javascript:(function(){const cookies=document.cookie.split(';').map(c=>{const [name,...valueParts]=c.trim().split('=');return {name:name,value:valueParts.join('='),domain:'.hitun.io',path:'/'};});if(!cookies.find(c=>c.name==='cf_clearance')){cookies.unshift({name:"cf_clearance",value:"在此粘贴你手动复制的_cf_clearance_值",domain:".hitun.io",path:"/"});}const jsonStr=JSON.stringify(cookies,null,2);const el=document.createElement('textarea');el.value=jsonStr;document.body.appendChild(el);el.select();document.execCommand('copy');document.body.removeChild(el);alert('✅ Cookies 已复制！还需要去 F12-Application-Cookies 里手动复制 cf_clearance 的值补全到 JSON 第一项。');})();
```
*注：`cf_clearance` 具有 HttpOnly 属性，脚本无法直接抓取，需手动在开发者工具的 Application 面板中找到它的 Value 并填入 JSON。*

### 2. 注入 Cookie
将生成的 JSON 内容保存为 `manual_cookies.json`，放入 `data/` 目录下。程序启动后会自动识别、注入并转存，从此一劳永逸。

---

## 💻 本地运行 (Python)

1. **安装依赖**：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **配置信息**：参考 `config.json.example` 创建 `config.json`。
3. **运行**：
   ```bash
   python hitun_checkin.py
   ```

---

## 📝 目录结构

```text
Hitun/
├── hitun_checkin.py    # 主程序逻辑
├── notification.py     # 消息通知模块
├── Dockerfile          # 镜像构建脚本
├── docker-compose.yml  # 容器编排配置
├── requirements.txt    # Python 依赖列表
├── scripts/            # 辅助脚本 (本地定时配置等)
├── data/               # 存放 config.json 和 cookies (已忽略)
└── logs/               # 存放签到日志 (已忽略)
```

## 🔒 安全提示

- 本项目不会上传任何用户的账号密码。
- `config.json` 和 `manual_cookies.json` 包含敏感信息，**绝对不要**提交到公共仓库。
- 已配置 `.gitignore` 自动忽略敏感文件。

## 📄 许可证

[MIT License](LICENSE)
