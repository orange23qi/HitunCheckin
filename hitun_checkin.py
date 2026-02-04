#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hitun.io 自动签到工具
每日自动登录并签到获取流量奖励
"""

import json
import logging
import os
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# 尝试导入 undetected-chromedriver (用于绑过 Cloudflare)
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

# 导入通知模块
try:
    from notification import create_notifier
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    logging.warning("通知模块不可用,将跳过推送功能")


class HitunCheckin:
    """Hitun.io 自动签到类"""

    # 页面加载重试配置
    MAX_PAGE_LOAD_RETRIES = 3
    PAGE_LOAD_RETRY_DELAY = 5  # 秒

    def __init__(self, config_path: str = "config.json"):
        """初始化签到工具

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.driver: Optional[webdriver.Chrome] = None
        self._setup_logging()
        
        # 初始化通知器
        self.notifier = None
        if NOTIFICATION_AVAILABLE:
            try:
                self.notifier = create_notifier(self.config)
                if self.notifier:
                    self.logger.info("Server酱推送已启用")
            except Exception as e:
                self.logger.warning(f"初始化通知器失败: {e}")
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                f"请复制 config.json.example 为 config.json 并填入登录信息"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证必需的配置项
        required_fields = ['email', 'password']
        for field in required_fields:
            if not config.get(field):
                raise ValueError(f"配置文件缺少必需字段: {field}")
        
        return config
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = Path(self.config.get('log_dir', 'logs'))
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / 'checkin.log'
        log_level = getattr(logging, self.config.get('log_level', 'INFO'))
        
        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置 logger
        self.logger = logging.getLogger('HitunCheckin')
        self.logger.setLevel(log_level)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _init_driver(self):
        """初始化 Chrome WebDriver

        优先使用 undetected-chromedriver 来绑过 Cloudflare 检测
        """
        use_uc = self.config.get('use_undetected_chrome', True) and UC_AVAILABLE
        headless = self.config.get('headless', True)

        if use_uc:
            self.logger.info("使用 undetected-chromedriver (反检测模式)")
            try:
                options = uc.ChromeOptions()

                # 无头模式
                if headless:
                    options.add_argument('--headless=new')

                # 基本配置
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')

                # 明确指定浏览器和驱动路径，避免下载挂起
                # 按优先级查找 chromium 可执行文件
                browser_candidates = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome-stable']
                browser_path = None
                for candidate in browser_candidates:
                    if os.path.exists(candidate):
                        browser_path = candidate
                        break

                driver_path = '/usr/bin/chromedriver'

                self.driver = uc.Chrome(
                    options=options,
                    browser_executable_path=browser_path,
                    driver_executable_path=driver_path if os.path.exists(driver_path) else None,
                    use_subprocess=True
                )
                self.driver.set_page_load_timeout(self.config.get('timeout', 60))
                self.logger.info("undetected-chromedriver 初始化成功")
                return
            except Exception as e:
                self.logger.warning(f"undetected-chromedriver 初始化失败: {e}")
                self.logger.info("回退到普通 Chrome WebDriver...")

        # 普通 Chrome WebDriver
        chrome_options = Options()

        # 无头模式配置
        if headless:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')

        # 其他优化选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # 禁用自动化检测
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            # 指定 chromium 二进制路径
            browser_candidates = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome-stable']
            for candidate in browser_candidates:
                if os.path.exists(candidate):
                    chrome_options.binary_location = candidate
                    break

            # 优先尝试使用已安装的 chromedriver
            if os.path.exists('/usr/bin/chromedriver'):
                service = Service('/usr/bin/chromedriver')
            else:
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            self.driver.set_page_load_timeout(self.config.get('timeout', 60))
            self.logger.info("WebDriver 初始化成功")
        except Exception as e:
            self.logger.error(f"WebDriver 初始化失败: {e}")
            raise
    
    def _wait_for_element(self, by: By, value: str, timeout: int = 10):
        """等待元素出现

        Args:
            by: 定位方式
            value: 定位值
            timeout: 超时时间(秒)

        Returns:
            找到的元素
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            self.logger.error(f"等待元素超时: {by}={value}")
            raise

    def _safe_get(self, url: str, retries: int = None) -> bool:
        """带重试的页面加载，处理 ERR_CONNECTION_CLOSED / timeout 等瞬态错误

        Args:
            url: 要访问的 URL
            retries: 重试次数，默认使用 MAX_PAGE_LOAD_RETRIES

        Returns:
            True 表示页面加载成功
        """
        if retries is None:
            retries = self.MAX_PAGE_LOAD_RETRIES

        for attempt in range(1, retries + 1):
            try:
                self.driver.get(url)
                return True
            except Exception as e:
                error_msg = str(e)
                is_transient = any(kw in error_msg for kw in [
                    'ERR_CONNECTION_CLOSED',
                    'ERR_CONNECTION_RESET',
                    'ERR_CONNECTION_REFUSED',
                    'ERR_NAME_NOT_RESOLVED',
                    'Timed out receiving message from renderer',
                    'timeout',
                    'net::ERR_',
                ])
                if is_transient and attempt < retries:
                    self.logger.warning(
                        f"页面加载失败 (尝试 {attempt}/{retries}): {error_msg[:120]}"
                    )
                    time.sleep(self.PAGE_LOAD_RETRY_DELAY * attempt)
                else:
                    self.logger.error(
                        f"页面加载最终失败 ({attempt}/{retries}): {error_msg[:200]}"
                    )
                    raise

    def _get_cookie_path(self) -> Path:
        """获取 cookie 文件路径"""
        data_dir = Path(self.config.get('data_dir', 'data'))
        data_dir.mkdir(exist_ok=True)
        return data_dir / 'cookies.pkl'

    def _inject_manual_cookies(self, cookies: list) -> bool:
        """注入手动提供的 cookies 并验证"""
        try:
            # 预访问域名
            self._safe_get("https://hitun.io")
            time.sleep(2)

            for cookie in cookies:
                # 关键修复：确保域名格式正确
                if 'domain' in cookie and not cookie['domain'].startswith('.'):
                    cookie['domain'] = '.' + cookie['domain']
                
                # 转换部分插件导出的格式字段
                if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                    del cookie['sameSite']
                
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.debug(f"注入 Cookie {cookie.get('name')} 失败: {e}")
            
            self.logger.info("手工 Cookies 注入完成，正在刷新验证...")
            self._safe_get("https://hitun.io/user") # 注入后直接跳转
            time.sleep(5)
            
            # 检查是否成功进入后台
            if "user" in self.driver.current_url or "dashboard" in self.driver.current_url:
                if "login" not in self.driver.current_url:
                    self.logger.info("✅ 手工 Cookies 验证成功!")
                    self._save_cookies() # 转存为 pkl 格式
                    return True
            
            self.logger.warning("手工 Cookies 注入后未能进入后台，可能已失效")
            return False
        except Exception as e:
            self.logger.error(f"手工 Cookies 注入过程出错: {e}")
            return False

    def _save_cookies(self):
        """保存当前会话的 cookies（过滤掉 Cloudflare 相关 cookies）"""
        try:
            cookie_path = self._get_cookie_path()
            cookies = self.driver.get_cookies()
            # 保留所有 cookies（包括 cf_clearance），同一 undetected-chromedriver 指纹可复用
            self.logger.info(f"保存 {len(cookies)} 个 cookies")
            with open(cookie_path, 'wb') as f:
                pickle.dump(cookies, f)
            self.logger.info(f"Cookies 已保存到: {cookie_path}")
        except Exception as e:
            self.logger.warning(f"保存 cookies 失败: {e}")

    def _load_cookies(self) -> bool:
        """加载保存的 cookies"""
        data_dir = Path(self.config.get('data_dir', 'data'))
        cookie_path = data_dir / 'cookies.pkl'
        json_cookie_path = data_dir / 'manual_cookies.json'

        if json_cookie_path.exists():
            try:
                self.logger.info(f"检测到手工注入的 Cookies 文件: {json_cookie_path}")
                with open(json_cookie_path, 'r', encoding='utf-8') as f:
                    manual_cookies = json.load(f)
                
                # 预访问域名
                self._safe_get("https://hitun.io")
                time.sleep(2)

                for cookie in manual_cookies:
                    if 'domain' in cookie and not cookie['domain'].startswith('.'):
                        cookie['domain'] = '.' + cookie['domain']
                    if 'sameSite' in cookie and cookie['sameSite'] not in ["Strict", "Lax", "None"]:
                        del cookie['sameSite']
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        self.logger.debug(f"注入 Cookie {cookie.get('name')} 失败: {e}")
                
                self.logger.info("手工 Cookies 注入完成，正在刷新验证...")
                self._safe_get("https://hitun.io/user")
                time.sleep(5)

                if "user" in self.driver.current_url or "dashboard" in self.driver.current_url:
                    self.logger.info("✅ 手工 Cookies 验证成功!")
                    self._save_cookies()
                    json_cookie_path.unlink()
                    return True
                else:
                    self.logger.warning("手工 Cookies 注入后未能进入后台，可能已失效")
            except Exception as e:
                self.logger.warning(f"手工 Cookies 注入失败: {e}")

        if not cookie_path.exists():
            self.logger.info("未找到保存的 cookies")
            return False

        try:
            with open(cookie_path, 'rb') as f:
                cookies = pickle.load(f)

            # 先访问目标域名（仅用于设置域，不等 CF 通过）
            self._safe_get("https://hitun.io")
            time.sleep(2)

            # 立即注入 cookies，不等 Cloudflare（和手动 cookies 流程一致）
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    self.logger.debug(f"添加 cookie 失败: {e}")

            self.logger.info(f"已注入 {len(cookies)} 个 cookies，正在导航验证...")

            # 注入后直接导航到用户页面验证
            self._safe_get("https://hitun.io/user")
            time.sleep(5)

            # 检查是否成功进入用户页面
            current_url = self.driver.current_url
            if ('user' in current_url or 'dashboard' in current_url) and 'login' not in current_url:
                self.logger.info("pkl Cookies 验证成功!")
                self._save_cookies()
                return True

            self.logger.warning("pkl Cookies 已失效")
            return False
        except Exception as e:
            self.logger.warning(f"加载 cookies 失败: {e}")
            return False

    def _check_cloudflare_challenge(self) -> bool:
        """检查是否遇到 Cloudflare 挑战

        Returns:
            True 表示遇到 Cloudflare 挑战
        """
        try:
            page_source = self.driver.page_source.lower()
            title = self.driver.title.lower()

            # 检测 Cloudflare 挑战页面的特征
            cf_indicators = [
                'checking your browser',
                'just a moment',
                'please wait',
                'cf-browser-verification',
                'cf_chl_opt',
                'turnstile',
                'cf-turnstile',
                'cloudflare'
            ]

            for indicator in cf_indicators:
                if indicator in page_source or indicator in title:
                    return True

            return False
        except Exception:
            return False

    def _wait_for_cloudflare(self, max_wait: int = 30) -> bool:
        """等待 Cloudflare 挑战完成

        Args:
            max_wait: 最大等待时间(秒)

        Returns:
            True 表示挑战已通过或不存在，False 表示超时
        """
        if not self._check_cloudflare_challenge():
            return True

        self.logger.warning("检测到 Cloudflare 挑战，等待自动验证...")
        start_time = time.time()

        while time.time() - start_time < max_wait:
            time.sleep(2)
            if not self._check_cloudflare_challenge():
                self.logger.info("Cloudflare 挑战已通过")
                return True
            self.logger.debug(f"等待 Cloudflare 验证中... ({int(time.time() - start_time)}s)")

        self.logger.error(f"Cloudflare 挑战等待超时 ({max_wait}s)")
        return False

    def _try_cookie_login(self) -> bool:
        """尝试使用保存的 cookies 登录"""
        if not self._load_cookies():
            return False

        try:
            # 检查 _load_cookies 是否已经验证成功（手工 cookies 流程会直接导航到 /user）
            current_url = self.driver.current_url
            if ('user' in current_url or 'dashboard' in current_url) and 'login' not in current_url:
                self.logger.info("Cookie 登录验证成功（已在用户页面）")
                return True

            # 只有未验证时才重新导航
            self._safe_get("https://hitun.io/user")
            time.sleep(5)

            # 等待可能的 Cloudflare 挑战
            cf_timeout = self.config.get('cloudflare_timeout', 60)
            if not self._wait_for_cloudflare(max_wait=cf_timeout):
                return False

            # 检查是否成功进入用户页面
            current_url = self.driver.current_url
            if ('user' in current_url or 'dashboard' in current_url) and 'login' not in current_url:
                self.logger.info("Cookie 登录验证成功")
                self._save_cookies()
                return True

            self.logger.info("Cookie 已失效，需要重新登录")
            return False
        except Exception as e:
            self.logger.warning(f"Cookie 登录失败: {e}")
            return False
    
    def login(self) -> bool:
        """登录到 Hitun.io

        Returns:
            登录是否成功
        """
        try:
            self.logger.info("开始登录流程...")

            # 首先尝试使用保存的 cookies 登录
            if self.config.get('use_cookies', True):
                if self._try_cookie_login():
                    return True
                self.logger.info("Cookie 登录失败，使用账号密码登录...")

            # 访问登录页面
            login_url = "https://hitun.io/auth/login"
            self._safe_get(login_url)
            self.logger.info(f"访问登录页面: {login_url}")

            # 等待可能的 Cloudflare 挑战
            cf_timeout = self.config.get('cloudflare_timeout', 30)
            if not self._wait_for_cloudflare(max_wait=cf_timeout):
                self.logger.error("无法通过 Cloudflare 验证")
                return False
            
            # 等待页面加载
            time.sleep(3)
            
            # 保存初始页面HTML用于调试
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            html_path = log_dir / f"login_page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.info(f"已保存登录页面HTML: {html_path}")
            
            # 检查是否有验证码
            page_source = self.driver.page_source
            if 'turnstile' in page_source.lower() or 'cf-turnstile' in page_source.lower():
                self.logger.warning("检测到 Cloudflare Turnstile 验证码")
            if 'recaptcha' in page_source.lower():
                self.logger.warning("检测到 reCAPTCHA 验证码")
            if 'hcaptcha' in page_source.lower():
                self.logger.warning("检测到 hCaptcha 验证码")
            
            # 输入邮箱
            email_input = self._wait_for_element(By.ID, 'email', timeout=15)
            email_input.clear()
            time.sleep(0.5)
            email_input.send_keys(self.config['email'])
            self.logger.info(f"输入邮箱: {self.config['email']}")
            time.sleep(1)
            
            # 输入密码
            password_input = self._wait_for_element(By.ID, 'passwd', timeout=15)
            password_input.clear()
            time.sleep(0.5)
            password_input.send_keys(self.config['password'])
            self.logger.info("输入密码")
            time.sleep(1)
            
            # 检查是否有验证码需要等待
            self.logger.info("等待可能的验证码处理...")
            time.sleep(5)  # 给验证码更多时间
            
            # 尝试多种方式点击登录按钮
            login_success = False
            
            # 方法1: 通过ID点击
            try:
                login_button = self._wait_for_element(By.ID, 'login', timeout=10)
                self.logger.info("找到登录按钮(通过ID)")
                
                # 滚动到按钮位置
                self.driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
                time.sleep(1)
                
                # 尝试点击
                login_button.click()
                self.logger.info("点击登录按钮(方法1: 直接点击)")
                login_success = True
            except Exception as e:
                self.logger.warning(f"方法1失败: {e}")
            
            # 方法2: 使用JavaScript点击
            if not login_success:
                try:
                    login_button = self.driver.find_element(By.ID, 'login')
                    self.driver.execute_script("arguments[0].click();", login_button)
                    self.logger.info("点击登录按钮(方法2: JavaScript点击)")
                    login_success = True
                except Exception as e:
                    self.logger.warning(f"方法2失败: {e}")
            
            # 方法3: 提交表单
            if not login_success:
                try:
                    form = self.driver.find_element(By.TAG_NAME, 'form')
                    self.driver.execute_script("arguments[0].submit();", form)
                    self.logger.info("提交登录表单(方法3: 表单提交)")
                    login_success = True
                except Exception as e:
                    self.logger.warning(f"方法3失败: {e}")
            
            if not login_success:
                self.logger.error("所有登录方法都失败了")
                return False
            
            # 等待登录完成,检查是否跳转到用户页面
            self.logger.info("等待登录响应...")
            time.sleep(5)
            
            # 检查是否有欢迎弹窗(登录成功后可能出现)
            try:
                # 查找可能的弹窗按钮
                popup_buttons = []
                
                # 尝试多种方式查找OK/确认按钮
                try:
                    # 查找包含"OK"或"确认"的按钮
                    popup_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'OK') or contains(text(), '确认') or contains(text(), '确定')]")
                except:
                    pass
                
                if not popup_buttons:
                    try:
                        # 查找swal2按钮(常见的弹窗库)
                        popup_buttons = self.driver.find_elements(By.CLASS_NAME, 'swal2-confirm')
                    except:
                        pass
                
                if not popup_buttons:
                    try:
                        # 查找其他常见的确认按钮
                        popup_buttons = self.driver.find_elements(By.XPATH, "//button[@class='confirm' or @class='btn-confirm']")
                    except:
                        pass
                
                # 如果找到弹窗按钮,点击它
                if popup_buttons:
                    for btn in popup_buttons:
                        try:
                            if btn.is_displayed():
                                self.logger.info(f"发现欢迎弹窗,点击确认按钮: {btn.text}")
                                btn.click()
                                time.sleep(2)
                                break
                        except:
                            pass
            except Exception as e:
                self.logger.debug(f"检查弹窗时出错(可忽略): {e}")
            
            # 多次检查URL变化和页面状态
            for i in range(3):
                current_url = self.driver.current_url
                self.logger.info(f"检查 {i+1}/3: 当前URL = {current_url}")
                
                # 检查URL是否包含user或dashboard
                if 'user' in current_url or 'dashboard' in current_url:
                    self.logger.info(f"✅ 登录成功! 当前页面: {current_url}")
                    # 保存 cookies 供下次使用
                    if self.config.get('use_cookies', True):
                        self._save_cookies()
                    return True
                
                # 即使URL没变,也检查页面内容是否显示已登录
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                    # 如果页面显示用户名或欢迎信息,说明登录成功
                    if '欢迎' in page_text or 'welcome' in page_text.lower():
                        # 检查是否在登录页面但显示欢迎信息(说明登录成功但未跳转)
                        if 'login' in current_url.lower():
                            self.logger.info("检测到登录成功(页面显示欢迎信息),尝试导航到用户页面...")
                            # 直接导航到用户页面
                            self._safe_get("https://hitun.io/user")
                            time.sleep(3)
                            if 'user' in self.driver.current_url:
                                self.logger.info(f"✅ 登录成功! 已导航到用户页面")
                                # 保存 cookies 供下次使用
                                if self.config.get('use_cookies', True):
                                    self._save_cookies()
                                return True
                except:
                    pass
                
                time.sleep(2)
            
            # 登录失败处理
            current_url = self.driver.current_url
            self.logger.error(f"❌ 登录失败,当前页面: {current_url}")
            
            # 保存失败截图
            screenshot_path = log_dir / f"login_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver.save_screenshot(str(screenshot_path))
            self.logger.info(f"已保存登录失败截图: {screenshot_path}")
            
            # 保存失败时的HTML
            html_fail_path = log_dir / f"login_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(html_fail_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.info(f"已保存失败页面HTML: {html_fail_path}")
            
            # 尝试查找错误信息
            try:
                # 查找可能的错误提示
                error_selectors = [
                    (By.CLASS_NAME, 'alert'),
                    (By.CLASS_NAME, 'error'),
                    (By.CLASS_NAME, 'message'),
                    (By.CLASS_NAME, 'alert-danger'),
                    (By.CLASS_NAME, 'alert-warning'),
                    (By.XPATH, "//*[contains(@class, 'alert')]"),
                    (By.XPATH, "//*[contains(@class, 'error')]"),
                ]
                
                for by, value in error_selectors:
                    try:
                        error_elements = self.driver.find_elements(by, value)
                        for elem in error_elements:
                            error_text = elem.text.strip()
                            if error_text:
                                self.logger.error(f"页面错误信息: {error_text}")
                    except:
                        pass
            except Exception as e:
                self.logger.warning(f"无法获取错误信息: {e}")
            
            # 检查页面源码中是否有提示
            page_source = self.driver.page_source
            
            # 验证码检测
            captcha_keywords = ['验证码', 'captcha', 'recaptcha', 'hcaptcha', 'turnstile', 'cf-turnstile']
            for keyword in captcha_keywords:
                if keyword in page_source.lower():
                    self.logger.error(f"⚠️ 检测到验证码关键词: {keyword}")
                    self.logger.error("建议: 1) 尝试关闭headless模式手动完成验证 2) 联系网站管理员")
                    break
            
            # 登录凭证检测
            if '密码错误' in page_source or '邮箱不存在' in page_source or 'incorrect' in page_source.lower():
                self.logger.error("⚠️ 登录凭证可能不正确,请检查 config.json 中的邮箱和密码")
            
            # 查找页面中的所有文本,帮助调试
            try:
                body_text = self.driver.find_element(By.TAG_NAME, 'body').text
                self.logger.info(f"页面可见文本(前500字符): {body_text[:500]}")
            except:
                pass
            
            return False
                
        except Exception as e:
            self.logger.error(f"登录过程出错: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def checkin(self) -> tuple[bool, Optional[str]]:
        """执行签到操作
        
        Returns:
            (签到是否成功, 获得的流量)
        """
        try:
            self.logger.info("开始签到流程...")
            
            # 确保在用户页面（避免不必要的导航触发 Cloudflare）
            current_url = self.driver.current_url
            if 'user' not in current_url and 'dashboard' not in current_url:
                self._safe_get("https://hitun.io/user")
                time.sleep(2)
            
            # 查找签到按钮 - 尝试多种方式定位
            checkin_button = None
            
            # 方法1: 通过按钮文本查找
            try:
                checkin_button = self.driver.find_element(
                    By.XPATH, 
                    "//button[contains(text(), '签到') or contains(text(), '>_ 签到')]"
                )
                self.logger.info("通过文本找到签到按钮")
            except NoSuchElementException:
                pass
            
            # 方法2: 通过 class 查找(根据截图,按钮可能有特定的 class)
            if not checkin_button:
                try:
                    # 等待签到区域加载
                    time.sleep(2)
                    buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                    for btn in buttons:
                        if '签到' in btn.text:
                            checkin_button = btn
                            self.logger.info("通过遍历按钮找到签到按钮")
                            break
                except Exception as e:
                    self.logger.warning(f"遍历按钮时出错: {e}")
            
            if not checkin_button:
                self.logger.error("未找到签到按钮")
                # 保存页面截图用于调试
                screenshot_path = f"logs/error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_path)
                self.logger.info(f"已保存错误截图: {screenshot_path}")
                return False, None
            
            # 检查按钮是否可点击
            if not checkin_button.is_enabled():
                # 可能已经签到过了
                self.logger.warning("签到按钮不可点击,可能今天已经签到过了")
                return True, None
            
            # 点击签到按钮
            checkin_button.click()
            self.logger.info("点击签到按钮")
            
            # 等待签到结果
            time.sleep(3)
            
            # 尝试获取签到结果信息
            traffic = None
            try:
                # 首先尝试从弹窗元素中提取流量信息
                try:
                    # 查找可能的弹窗元素
                    popup_selectors = [
                        (By.CLASS_NAME, 'swal2-html-container'),
                        (By.CLASS_NAME, 'swal2-content'),
                        (By.CLASS_NAME, 'modal-body'),
                        (By.CLASS_NAME, 'alert'),
                        (By.XPATH, "//*[contains(@class, 'message')]"),
                    ]
                    
                    popup_text = None
                    for by, value in popup_selectors:
                        try:
                            elements = self.driver.find_elements(by, value)
                            for elem in elements:
                                if elem.is_displayed():
                                    text = elem.text.strip()
                                    if text and ('获得' in text or '奖励' in text or '流量' in text):
                                        popup_text = text
                                        self.logger.info(f"找到弹窗消息: {popup_text}")
                                        break
                            if popup_text:
                                break
                        except:
                            pass
                    
                    # 从弹窗文本中提取流量
                    if popup_text:
                        import re
                        # 尝试多种匹配模式
                        patterns = [
                            r'获得[了]?\s*(\d+)\s*M',  # 获得 XXM 或 获得了 XXM
                            r'奖励[了]?\s*(\d+)\s*M',  # 奖励 XXM
                            r'(\d+)\s*M[B]?\s*流量',   # XXM流量 或 XXMB流量
                            r'流量[：:]\s*(\d+)\s*M',  # 流量: XXM
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, popup_text)
                            if match:
                                traffic = match.group(1)
                                self.logger.info(f"✅ 从弹窗提取到流量: {traffic}M (模式: {pattern})")
                                break
                except Exception as e:
                    self.logger.debug(f"从弹窗提取流量失败: {e}")
                
                # 如果从弹窗提取失败,尝试从页面源码提取
                if not traffic:
                    page_source = self.driver.page_source
                    self.logger.debug(f"页面源码片段(用于调试): {page_source[page_source.find('签到') if '签到' in page_source else 0:page_source.find('签到')+500 if '签到' in page_source else 500]}")
                    
                    import re
                    # 尝试多种匹配模式
                    patterns = [
                        r'获得[了]?\s*(\d+)\s*M',
                        r'奖励[了]?\s*(\d+)\s*M',
                        r'(\d+)\s*M[B]?\s*流量',
                        r'流量[：:]\s*(\d+)\s*M',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, page_source)
                        if match:
                            traffic = match.group(1)
                            self.logger.info(f"✅ 从页面源码提取到流量: {traffic}M (模式: {pattern})")
                            break
                
                # 检查是否有成功提示
                page_source = self.driver.page_source
                if '签到成功' in page_source or '获得' in page_source:
                    self.logger.info("✅ 签到成功!")
                    if traffic:
                        self.logger.info(f"🎉 获得流量: {traffic}M")
                    else:
                        self.logger.warning("⚠️ 未能提取到流量信息,请检查页面结构")
                    return True, traffic
                else:
                    self.logger.warning("签到操作完成,但未确认结果")
                    return True, traffic
                    
            except Exception as e:
                self.logger.warning(f"获取签到结果时出错: {e}")
                # 即使获取结果失败,也认为签到成功
                return True, traffic
                
        except Exception as e:
            self.logger.error(f"签到过程出错: {e}")
            return False, None
    
    def _run_once(self) -> tuple[bool, Optional[str]]:
        """执行一次完整的签到流程（初始化浏览器 -> 登录 -> 签到）

        Returns:
            (是否成功, 获得的流量)
        """
        traffic = None
        try:
            # 初始化浏览器
            self._init_driver()

            # 登录
            if not self.login():
                self.logger.error("登录失败")
                return False, None

            # 签到
            checkin_success, traffic = self.checkin()
            if checkin_success:
                self.logger.info("✅ 签到流程完成!")
                return True, traffic
            else:
                self.logger.error("❌ 签到失败")
                return False, traffic

        except Exception as e:
            self.logger.error(f"执行过程中发生错误: {e}")
            return False, traffic
        finally:
            # 清理资源
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                self.logger.info("浏览器已关闭")

    def run(self) -> bool:
        """运行完整的签到流程，失败时自动重试

        Returns:
            整体流程是否成功
        """
        max_attempts = self.config.get('max_retry', 3)
        retry_delay = 30  # 重试间隔（秒）
        success = False
        traffic = None

        self.logger.info("=" * 50)
        self.logger.info(f"开始执行签到任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 50)

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                self.logger.info(f"--- 第 {attempt}/{max_attempts} 次尝试 (等待 {retry_delay}s) ---")
                time.sleep(retry_delay)

            success, traffic = self._run_once()
            if success:
                break

            self.logger.warning(f"第 {attempt}/{max_attempts} 次尝试失败")

        self.logger.info("=" * 50)
        self.logger.info(f"任务结束 - 状态: {'成功' if success else '失败'}")
        self.logger.info("=" * 50)

        # 发送推送通知
        if self.notifier:
            try:
                if success:
                    traffic_str = f"{traffic}M" if traffic else None
                    self.notifier.send_checkin_success(
                        traffic=traffic_str,
                        details=f"签到时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                else:
                    self.notifier.send_checkin_failure(
                        error_msg="签到流程执行失败",
                        details=f"失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n请查看日志文件获取详细信息"
                    )
            except Exception as e:
                self.logger.warning(f"发送推送通知失败: {e}")

        return success


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Hitun.io 自动签到工具')
    parser.add_argument(
        '--config',
        default='config.json',
        help='配置文件路径 (默认: config.json)'
    )
    parser.add_argument(
        '--test-login',
        action='store_true',
        help='仅测试登录功能'
    )
    
    args = parser.parse_args()
    
    try:
        checkin = HitunCheckin(config_path=args.config)
        
        if args.test_login:
            # 仅测试登录
            checkin._init_driver()
            success = checkin.login()
            if success:
                print("✅ 登录测试成功!")
                time.sleep(3)  # 让用户看到登录后的页面
            else:
                print("❌ 登录测试失败!")
            checkin.driver.quit()
            sys.exit(0 if success else 1)
        else:
            # 完整签到流程
            success = checkin.run()
            sys.exit(0 if success else 1)
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
