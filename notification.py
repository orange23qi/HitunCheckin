#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知推送模块
支持Server酱(ServerChan)推送服务
"""

import logging
import requests
from typing import Optional


class ServerChanNotifier:
    """Server酱推送通知类"""
    
    def __init__(self, sendkey: str, uid: str = "1611", timeout: int = 10):
        """初始化Server酱推送器
        
        Args:
            sendkey: Server酱的SendKey
            uid: Server酱³的用户UID
            timeout: 请求超时时间(秒)
        """
        self.sendkey = sendkey
        self.uid = uid
        self.timeout = timeout
        self.api_url = f"https://{uid}.push.ft07.com/send/{sendkey}.send"
        self.logger = logging.getLogger('ServerChanNotifier')
    
    def send_notification(self, title: str, content: str = "", channel: Optional[str] = None) -> bool:
        """发送推送通知
        
        Args:
            title: 通知标题
            content: 通知内容(支持Markdown格式)
            channel: 可选的推送渠道
            
        Returns:
            是否发送成功
        """
        try:
            # 构建请求参数
            params = {
                'title': title,
                'desp': content
            }
            
            if channel:
                params['channel'] = channel
            
            # 发送请求
            self.logger.info(f"正在发送Server酱推送: {title}")
            response = requests.get(self.api_url, params=params, timeout=self.timeout)
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    self.logger.info(f"✅ 推送发送成功! PushID: {result.get('data', {}).get('pushid', 'N/A')}")
                    return True
                else:
                    self.logger.error(f"推送失败: {result.get('message', '未知错误')}")
                    return False
            else:
                self.logger.error(f"推送请求失败: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error(f"推送请求超时({self.timeout}秒)")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"推送请求异常: {e}")
            return False
        except Exception as e:
            self.logger.error(f"推送发送失败: {e}")
            return False
    
    def send_checkin_success(self, traffic: Optional[str] = None, details: str = "") -> bool:
        """发送签到成功通知
        
        Args:
            traffic: 获得的流量(如: "100M")
            details: 额外的详细信息
            
        Returns:
            是否发送成功
        """
        title = "✅ Hitun.io 签到成功"
        
        content_parts = ["签到已完成!"]
        
        if traffic:
            content_parts.append(f"\n🎉 **获得流量**: {traffic}")
        
        if details:
            content_parts.append(f"\n\n**详情**:\n{details}")
        
        content = "\n".join(content_parts)
        
        return self.send_notification(title, content)
    
    def send_checkin_failure(self, error_msg: str, details: str = "") -> bool:
        """发送签到失败通知
        
        Args:
            error_msg: 错误信息
            details: 额外的详细信息
            
        Returns:
            是否发送成功
        """
        title = "❌ Hitun.io 签到失败"
        
        content_parts = [f"签到失败: {error_msg}"]
        
        if details:
            content_parts.append(f"\n\n**详情**:\n{details}")
        
        content_parts.append("\n\n请检查日志文件获取更多信息。")
        
        content = "\n".join(content_parts)
        
        return self.send_notification(title, content)


def create_notifier(config: dict) -> Optional[ServerChanNotifier]:
    """根据配置创建通知器
    
    Args:
        config: 配置字典
        
    Returns:
        ServerChanNotifier实例,如果未启用则返回None
    """
    if not config.get('enable_notification', False):
        return None
    
    sendkey = config.get('serverchan_key', '').strip()
    if not sendkey:
        logging.warning("Server酱推送已启用但未配置SendKey,将跳过推送")
        return None
    
    uid = config.get('serverchan_uid', '1611').strip()
    timeout = config.get('notification_timeout', 10)
    return ServerChanNotifier(sendkey, uid, timeout)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python3 notification.py <SENDKEY> [title] [content]")
        sys.exit(1)
    
    sendkey = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "测试通知"
    content = sys.argv[3] if len(sys.argv) > 3 else "这是一条测试消息"
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 发送测试通知
    notifier = ServerChanNotifier(sendkey, uid="1611")
    success = notifier.send_notification(title, content)
    
    sys.exit(0 if success else 1)
