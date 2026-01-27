#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录调试工具 - 非headless模式,可以手动处理验证码
"""

import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def debug_login():
    """调试登录流程"""
    
    # 加载配置
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 设置Chrome选项 - 非headless模式
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # 初始化浏览器
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print("=" * 60)
        print("登录调试工具 - 可视化模式")
        print("=" * 60)
        
        # 访问登录页面
        login_url = "https://hitun.io/auth/login"
        driver.get(login_url)
        print(f"✓ 已打开登录页面: {login_url}")
        time.sleep(3)
        
        # 保存初始页面HTML
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        html_path = log_dir / "debug_login_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"✓ 已保存页面HTML: {html_path}")
        
        # 检查验证码
        page_source = driver.page_source
        captcha_found = False
        
        if 'turnstile' in page_source.lower() or 'cf-turnstile' in page_source.lower():
            print("⚠️  检测到 Cloudflare Turnstile 验证码")
            captcha_found = True
        if 'recaptcha' in page_source.lower():
            print("⚠️  检测到 reCAPTCHA 验证码")
            captcha_found = True
        if 'hcaptcha' in page_source.lower():
            print("⚠️  检测到 hCaptcha 验证码")
            captcha_found = True
        
        if captcha_found:
            print("\n" + "=" * 60)
            print("发现验证码!")
            print("请在浏览器窗口中手动完成验证码验证")
            print("完成后按回车继续...")
            print("=" * 60)
            input()
        
        # 输入邮箱
        email_input = driver.find_element(By.ID, 'email')
        email_input.clear()
        email_input.send_keys(config['email'])
        print(f"✓ 已输入邮箱: {config['email']}")
        time.sleep(1)
        
        # 输入密码
        password_input = driver.find_element(By.ID, 'passwd')
        password_input.clear()
        password_input.send_keys(config['password'])
        print("✓ 已输入密码")
        time.sleep(1)
        
        # 如果还有验证码,等待用户处理
        if captcha_found:
            print("\n" + "=" * 60)
            print("请确认验证码已完成,然后按回车继续...")
            print("=" * 60)
            input()
        
        # 点击登录按钮
        login_button = driver.find_element(By.ID, 'login')
        print("✓ 找到登录按钮,准备点击...")
        
        # 滚动到按钮位置
        driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
        time.sleep(1)
        
        # 点击登录
        login_button.click()
        print("✓ 已点击登录按钮")
        
        # 等待页面跳转
        print("\n等待登录响应...")
        for i in range(10):
            time.sleep(1)
            current_url = driver.current_url
            print(f"  [{i+1}/10] 当前URL: {current_url}")
            
            if 'user' in current_url or 'dashboard' in current_url:
                print("\n" + "=" * 60)
                print("✅ 登录成功!")
                print(f"当前页面: {current_url}")
                print("=" * 60)
                
                # 保存成功页面
                screenshot_path = log_dir / "login_success.png"
                driver.save_screenshot(str(screenshot_path))
                print(f"✓ 已保存成功截图: {screenshot_path}")
                
                html_success_path = log_dir / "login_success.html"
                with open(html_success_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print(f"✓ 已保存成功页面HTML: {html_success_path}")
                
                print("\n浏览器将在10秒后关闭...")
                time.sleep(10)
                return True
        
        # 登录失败
        print("\n" + "=" * 60)
        print("❌ 登录失败")
        print(f"当前页面: {driver.current_url}")
        print("=" * 60)
        
        # 保存失败信息
        screenshot_path = log_dir / "debug_login_failed.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"✓ 已保存失败截图: {screenshot_path}")
        
        html_fail_path = log_dir / "debug_login_failed.html"
        with open(html_fail_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"✓ 已保存失败页面HTML: {html_fail_path}")
        
        # 显示页面文本
        try:
            body_text = driver.find_element(By.TAG_NAME, 'body').text
            print(f"\n页面可见文本:\n{body_text[:500]}")
        except:
            pass
        
        print("\n浏览器将在30秒后关闭,请检查页面...")
        time.sleep(30)
        return False
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        print(traceback.format_exc())
        
        print("\n浏览器将在30秒后关闭...")
        time.sleep(30)
        return False
        
    finally:
        driver.quit()
        print("\n浏览器已关闭")

if __name__ == '__main__':
    debug_login()
