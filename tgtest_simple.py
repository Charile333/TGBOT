"""
Telegram 机器人测试程序 - 简化版本（使用 requests 直接调用 API）
不依赖 python-telegram-bot 库，避免 Python 3.13 兼容性问题

这个版本直接使用 Telegram Bot API，完全兼容 Python 3.13
集成账密泄露产品 API 查询功能
"""

import requests
import time
import json
import re
import os
import csv
from typing import Optional, Dict, Any, List, Union

import urllib.request
import urllib3

# 禁用安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Telegram Bot API 配置
# 优先从环境变量读取
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ 错误: 未设置 TELEGRAM_TOKEN 环境变量")
    print("请设置环境变量: set TELEGRAM_TOKEN=你的BotToken")
    # 为了防止程序直接崩溃，这里可以抛出异常或者让 main 函数处理
    # 但为了简单起见，如果是在 main 中检测会更好，这里先留空，main 函数会检查连接
    
API_BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# 自动检测代理配置
PROXIES = urllib.request.getproxies()
if PROXIES:
    print(f"检测到系统代理: {PROXIES}")
else:
    print("未检测到系统代理，尝试直接连接")

# ============================================================================
# API 配置
# ============================================================================
# API 速率限制：30 请求/秒

# API 基础地址
LEAK_API_BASE_URL = "https://api.leakradar.io"

# API Key（Bearer Token）
# 优先从环境变量读取
LEAK_API_KEY = os.environ.get("LEAK_API_KEY")
if not LEAK_API_KEY:
    print("❌ 错误: 未设置 LEAK_API_KEY 环境变量")
    print("请设置环境变量: set LEAK_API_KEY=你的APIKey")

# API 请求头（Bearer Token 认证）
LEAK_API_HEADERS = {
    "Authorization": f"Bearer {LEAK_API_KEY}"
}

# 全局变量
last_update_id = 0

def delete_webhook() -> bool:
    """删除 Webhook 配置，确保 getUpdates 可用"""
    url = f"{API_BASE_URL}/deleteWebhook"
    try:
        response = requests.get(url, timeout=10, proxies=PROXIES, verify=False)
        result = response.json()
        if result.get("ok"):
            print("✓ Webhook 已清除")
            return True
        else:
            print(f"⚠ 清除 Webhook 失败: {result}")
            return False
    except Exception as e:
        print(f"⚠ 清除 Webhook 出错: {e}")
        return False

def get_updates(timeout: int = 30, offset: Optional[int] = None) -> Dict[str, Any]:
    """获取更新消息"""
    print(f"[DEBUG] 开始获取更新... timeout={timeout}", flush=True)
    url = f"{API_BASE_URL}/getUpdates"
    params = {
        "timeout": timeout
    }
    if offset:
        params["offset"] = offset
        # print(f"[DEBUG] 使用 offset: {offset}")
    else:
        # 如果没有 offset，尝试获取所有未确认的消息
        params["offset"] = -1
        # print(f"[DEBUG] 使用默认 offset: -1")
    
    try:
        # 增加 verify=False 避免某些证书问题，但会由警告
        # 也可以尝试自动检测代理，这里先保持简单
        response = requests.get(url, params=params, timeout=timeout + 10, proxies=PROXIES, verify=False)
        response.raise_for_status()
        data = response.json()
        if not data.get("result"):
             print(f"[DEBUG] 暂无新消息", flush=True)
        else:
             print(f"[DEBUG] 收到消息: {json.dumps(data, ensure_ascii=False)}", flush=True)
        return data
    except requests.exceptions.RequestException as e:
        print(f"获取更新失败: {e}")
        # 如果是连接错误，提示用户检查网络
        if "Connect" in str(e) or "Read timed out" in str(e):
            print("💡 提示: 请检查网络连接或代理设置 (Telegram API 需要翻墙)")
        return {"ok": False, "result": []}

def send_message(chat_id: int, text: str) -> bool:
    """发送消息"""
    url = f"{API_BASE_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        response = requests.post(url, json=data, timeout=10, proxies=PROXIES, verify=False)
        response.raise_for_status()
        return response.json().get("ok", False)
    except requests.exceptions.RequestException as e:
        print(f"发送消息失败: {e}")
        return False

def send_document(chat_id: int, file_path: str, caption: str = "") -> bool:
    """发送文件（文档）"""
    url = f"{API_BASE_URL}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            files = {'document': (os.path.basename(file_path), f, 'text/csv')}
            data = {
                'chat_id': chat_id,
                'caption': caption[:1024] if caption else ""  # Telegram 限制 caption 长度
            }
            response = requests.post(url, files=files, data=data, timeout=120, proxies=PROXIES, verify=False)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                print(f"发送文件失败: {result}")
                return False
            return True
    except requests.exceptions.RequestException as e:
        print(f"发送文件失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"错误详情: {error_detail}")
            except:
                pass
        return False
    except Exception as e:
        print(f"发送文件出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def is_valid_domain(domain: str) -> bool:
    """验证域名格式是否有效"""
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    return bool(domain_pattern.match(domain.strip()))

def normalize_domain(domain: str) -> str:
    """规范化域名（去除协议、路径等）"""
    domain = domain.strip()
    # 移除 http:// 或 https://
    domain = re.sub(r'^https?://', '', domain)
    # 移除 www.
    domain = re.sub(r'^www\.', '', domain)
    # 移除路径和查询参数
    domain = domain.split('/')[0]
    domain = domain.split('?')[0]
    # 移除端口号
    domain = domain.split(':')[0]
    return domain.strip().lower()

def query_leak_api(domain: str) -> Dict[str, Any]:
    """
    调用 API 查询域名泄露情况
    
    API 端点: GET /search/domain/{domain}
    返回域名的泄露报告，包括员工、客户和第三方的泄露数量
    
    Args:
        domain: 要查询的域名
        
    Returns:
        API 返回的 JSON 数据，如果出错则返回包含 'error' 键的字典
    """
    try:
        # API: GET /search/domain/{domain}
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}"
        
        # 可选参数：light=true 返回简化版本（不需要认证）
        # light=false 返回完整版本（需要认证，包括密码统计）
        params = {"light": False}  # 使用完整版本（需要 API Key）
        
        response = requests.get(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        # 检查 HTTP 状态码
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key 是否正确"}
        elif response.status_code == 404:
            return {"error": "域名未找到或没有相关数据"}
        elif response.status_code == 422:
            return {"error": "域名格式验证失败"}
        
        response.raise_for_status()
        result = response.json()
        print(f"[API] 查询域名 {domain} 成功")
        return result
        
    except requests.exceptions.Timeout:
        print(f"[API] 查询域名 {domain} 超时")
        return {"error": "请求超时，请稍后重试"}
    except requests.exceptions.HTTPError as e:
        error_msg = f"API 返回错误: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            if "detail" in error_detail:
                error_msg += f" - {error_detail['detail']}"
        except:
            pass
        print(f"[API] {error_msg}")
        return {"error": error_msg}
    except requests.exceptions.RequestException as e:
        print(f"[API] 查询域名 {domain} 失败: {e}")
        return {"error": f"API 请求失败: {str(e)}"}
    except json.JSONDecodeError as e:
        print(f"[API] 解析响应失败: {e}")
        return {"error": "API 返回格式错误，无法解析 JSON"}
    except Exception as e:
        print(f"[API] 未知错误: {e}")
        return {"error": f"查询时发生错误: {str(e)}"}

def query_domain_leaks(domain: str, leak_type: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    查询域名的详细泄露列表
    
    API 端点: GET /search/domain/{domain}/{leak_type}
    leak_type: employees, customers, third_parties
    
    Args:
        domain: 域名
        leak_type: 泄露类型 (employees/customers/third_parties)
        page: 页码（从1开始）
        page_size: 每页数量（1-1000）
        
    Returns:
        API 返回的 JSON 数据
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}/{leak_type}"
        params = {
            "page": page,
            "page_size": min(page_size, 100)  # 限制最大100条，避免消息过长
        }
        
        response = requests.get(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 404:
            return {"error": "未找到相关数据"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 查询 {leak_type} 泄露失败: {e}")
        return {"error": f"查询失败: {str(e)}"}

def query_email_leaks(email: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    通过邮箱或用户名查询泄露
    
    API 端点: POST /search/email
    
    Args:
        email: 邮箱地址或用户名
        page: 页码
        page_size: 每页数量
        
    Returns:
        API 返回的 JSON 数据
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/email"
        params = {
            "page": page,
            "page_size": min(page_size, 100)
        }
        payload = {
            "email": email
        }
        
        response = requests.post(
            url,
            params=params,
            json=payload,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 404:
            return {"error": "未找到相关数据"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 查询邮箱泄露失败: {e}")
        return {"error": f"查询失败: {str(e)}"}

def unlock_domain_leaks(domain: str, leak_type: str, max_items: int = 10000) -> Union[List[Any], Dict[str, Any]]:
    """
    解锁域名泄露数据
    
    API 端点: POST /search/domain/{domain}/{leak_type}/unlock
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}/{leak_type}/unlock"
        print(f"[API] 正在尝试解锁: {url}")
        
        # 增加 max 参数
        params = {"max": max_items}
        
        response = requests.post(
            url,
            headers=LEAK_API_HEADERS,
            params=params,
            timeout=60,
            proxies=PROXIES,
            verify=False
        )

        
        if response.status_code == 401:
            return {"error": "API 认证失败"}
        elif response.status_code == 403:
            return {"error": "权限不足或积分不够"}
        
        # 404 可能表示没有可解锁的数据，但也算是成功的一种（没报错）
        if response.status_code == 404:
             print(f"[API] 没有需要解锁的数据")
             return []

        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 解锁失败: {e}")
        return {"error": str(e)}

def unlock_email_leaks(email: str, max_items: int = 10000) -> Union[List[Any], Dict[str, Any]]:
    """
    解锁邮箱泄露数据
    
    API 端点: POST /search/email/unlock
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/email/unlock"
        payload = {
            "email": email,
            "max": max_items
        }
        
        response = requests.post(
            url,
            json=payload,
            headers=LEAK_API_HEADERS,
            timeout=60,
            proxies=PROXIES,
            verify=False
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败"}
        
        if response.status_code == 404:
             print(f"[API] 没有需要解锁的数据")
             return []

        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 解锁失败: {e}")
        return {"error": str(e)}

def query_domain_subdomains(domain: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    查询域名的子域名列表
    
    API 端点: GET /search/domain/{domain}/subdomains
    
    Args:
        domain: 域名
        page: 页码
        page_size: 每页数量
        
    Returns:
        API 返回的 JSON 数据
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}/subdomains"
        params = {
            "page": page,
            "page_size": min(page_size, 100)
        }
        
        response = requests.get(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 404:
            return {"error": "未找到相关数据"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 查询子域名失败: {e}")
        return {"error": f"查询失败: {str(e)}"}

def query_domain_urls(domain: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    查询域名相关的 URL 列表
    
    API 端点: GET /search/domain/{domain}/urls
    
    Args:
        domain: 域名
        page: 页码
        page_size: 每页数量
        
    Returns:
        API 返回的 JSON 数据
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}/urls"
        params = {
            "page": page,
            "page_size": min(page_size, 100)
        }
        
        response = requests.get(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 404:
            return {"error": "未找到相关数据"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 查询 URL 失败: {e}")
        return {"error": f"查询失败: {str(e)}"}

def fetch_all_domain_leaks(domain: str, leak_type: str, max_items: int = 10000) -> List[Dict[str, Any]]:
    """
    获取所有域名泄露数据（自动翻页）
    """
    all_items = []
    page = 1
    page_size = 100
    
    print(f"[Fetch] 开始获取 {domain} 的 {leak_type} 数据...")
    
    while True:
        if len(all_items) >= max_items:
            break
            
        result = query_domain_leaks(domain, leak_type, page, page_size)
        if "error" in result:
            print(f"[Fetch] 获取第 {page} 页失败: {result['error']}")
            break
            
        items = result.get("items", [])
        if not items:
            break
            
        all_items.extend(items)
        print(f"[Fetch] 已获取 {len(all_items)} 条数据 (Page {page})")
        
        if len(items) < page_size:
            break
            
        page += 1
        time.sleep(0.5)  # 避免过快请求
        
    return all_items

def fetch_all_email_leaks(email: str, max_items: int = 10000) -> List[Dict[str, Any]]:
    """
    获取所有邮箱泄露数据（自动翻页）
    """
    all_items = []
    page = 1
    page_size = 100
    
    print(f"[Fetch] 开始获取 {email} 的数据...")
    
    while True:
        if len(all_items) >= max_items:
            break
            
        result = query_email_leaks(email, page, page_size)
        if "error" in result:
            print(f"[Fetch] 获取第 {page} 页失败: {result['error']}")
            break
            
        items = result.get("items", [])
        if not items:
            break
            
        all_items.extend(items)
        print(f"[Fetch] 已获取 {len(all_items)} 条数据 (Page {page})")
        
        if len(items) < page_size:
            break
            
        page += 1
        time.sleep(0.5)
        
    return all_items

def create_csv_file(data: List[Dict[str, Any]], filename_prefix: str) -> Optional[str]:
    """
    创建 CSV 文件
    """
    if not data:
        return None
        
    try:
        # 确定字段
        # 根据实际数据调整字段
        headers = ["username", "password", "url", "is_email", "unlocked", "password_strength", "added_at"]
        
        # 创建临时目录
        temp_dir = "temp_exports"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        filename = f"{filename_prefix}_{int(time.time())}.csv"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
            
        print(f"[CSV] 文件已创建: {file_path}")
        return file_path
    except Exception as e:
        print(f"[CSV] 创建失败: {e}")
        return None

def format_api_result(api_result: Dict[str, Any], domain: str) -> str:
    """
    格式化 API 返回结果，转换为用户友好的消息
    
    API 响应格式：
    - DomainSearchResponse: employees_compromised, third_parties_compromised, customers_compromised
    - 可选的密码统计：employee_passwords, third_parties_passwords, customer_passwords
    - blacklisted_value: 黑名单值（如果有）
    
    Args:
        api_result: API 返回的数据
        domain: 查询的域名
        
    Returns:
        格式化后的消息文本
    """
    # 如果 API 返回错误
    if "error" in api_result:
        return f"❌ 查询失败\n\n域名: {domain}\n错误: {api_result['error']}"
    
    try:
        message_parts = [f"🔍 域名泄露查询结果: {domain}\n"]
        message_parts.append("=" * 40)
        
        # 提取泄露数量
        employees = api_result.get("employees_compromised", 0)
        third_parties = api_result.get("third_parties_compromised", 0)
        customers = api_result.get("customers_compromised", 0)
        
        total_leaks = employees + third_parties + customers
        
        if total_leaks > 0:
            message_parts.append(f"\n⚠️ 发现泄露记录\n")
            message_parts.append(f"👤 员工泄露: {employees} 条")
            message_parts.append(f"🤝 第三方泄露: {third_parties} 条")
            message_parts.append(f"👥 客户泄露: {customers} 条")
            message_parts.append(f"\n📊 总计: {total_leaks} 条泄露记录")
        else:
            message_parts.append(f"\n✅ 未发现泄露记录")
            message_parts.append(f"👤 员工泄露: 0 条")
            message_parts.append(f"🤝 第三方泄露: 0 条")
            message_parts.append(f"👥 客户泄露: 0 条")
        
        # 如果有密码统计信息（完整版本响应）
        if "employee_passwords" in api_result:
            message_parts.append(f"\n📈 密码强度统计:")
            
            # 员工密码统计
            emp_pwd = api_result.get("employee_passwords", {})
            if isinstance(emp_pwd, dict) and emp_pwd.get("total_pass", 0) > 0:
                message_parts.append(f"\n👤 员工密码:")
                too_weak = emp_pwd.get('too_weak', {}) or {}
                weak = emp_pwd.get('weak', {}) or {}
                medium = emp_pwd.get('medium', {}) or {}
                strong = emp_pwd.get('strong', {}) or {}
                message_parts.append(f"   • 太弱: {too_weak.get('qty', 0)} ({too_weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 弱: {weak.get('qty', 0)} ({weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 中等: {medium.get('qty', 0)} ({medium.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 强: {strong.get('qty', 0)} ({strong.get('perc', 0):.1f}%)")
            
            # 第三方密码统计
            third_pwd = api_result.get("third_parties_passwords", {})
            if isinstance(third_pwd, dict) and third_pwd.get("total_pass", 0) > 0:
                message_parts.append(f"\n🤝 第三方密码:")
                too_weak = third_pwd.get('too_weak', {}) or {}
                weak = third_pwd.get('weak', {}) or {}
                medium = third_pwd.get('medium', {}) or {}
                strong = third_pwd.get('strong', {}) or {}
                message_parts.append(f"   • 太弱: {too_weak.get('qty', 0)} ({too_weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 弱: {weak.get('qty', 0)} ({weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 中等: {medium.get('qty', 0)} ({medium.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 强: {strong.get('qty', 0)} ({strong.get('perc', 0):.1f}%)")
            
            # 客户密码统计
            cust_pwd = api_result.get("customer_passwords", {})
            if isinstance(cust_pwd, dict) and cust_pwd.get("total_pass", 0) > 0:
                message_parts.append(f"\n👥 客户密码:")
                too_weak = cust_pwd.get('too_weak', {}) or {}
                weak = cust_pwd.get('weak', {}) or {}
                medium = cust_pwd.get('medium', {}) or {}
                strong = cust_pwd.get('strong', {}) or {}
                message_parts.append(f"   • 太弱: {too_weak.get('qty', 0)} ({too_weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 弱: {weak.get('qty', 0)} ({weak.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 中等: {medium.get('qty', 0)} ({medium.get('perc', 0):.1f}%)")
                message_parts.append(f"   • 强: {strong.get('qty', 0)} ({strong.get('perc', 0):.1f}%)")
        
        # 黑名单值（如果有）
        if api_result.get("blacklisted_value"):
            message_parts.append(f"\n⚠️ 黑名单值: {api_result['blacklisted_value']}")
        
        result_message = "\n".join(message_parts)
        
        # Telegram 消息长度限制（约 4096 字符）
        if len(result_message) > 4000:
            result_message = result_message[:3900] + "\n\n... (内容过长，已截断)"
        
        return result_message
        
    except Exception as e:
        # 如果格式化失败，返回原始 JSON
        print(f"[格式化] 格式化结果失败: {e}")
        import traceback
        traceback.print_exc()
        return f"📋 域名: {domain}\n\n原始响应:\n{json.dumps(api_result, indent=2, ensure_ascii=False)}"

def format_leaks_list(api_result: Dict[str, Any], leak_type: str, domain: str = "") -> str:
    """
    格式化泄露列表结果
    
    Args:
        api_result: API 返回的数据
        leak_type: 泄露类型
        domain: 域名（可选）
        
    Returns:
        格式化后的消息文本
    """
    if "error" in api_result:
        return f"❌ 查询失败\n\n错误: {api_result['error']}"
    
    try:
        items = api_result.get("items", [])
        total = api_result.get("total", 0)
        total_unlocked = api_result.get("total_unlocked", 0)
        page = api_result.get("page", 1)
        page_size = api_result.get("page_size", 10)
        
        type_names = {
            "employees": "员工",
            "customers": "客户",
            "third_parties": "第三方"
        }
        type_name = type_names.get(leak_type, leak_type)
        
        message_parts = [f"📋 {type_name}泄露列表"]
        if domain:
            message_parts.append(f"域名: {domain}")
        message_parts.append("=" * 40)
        message_parts.append(f"\n📊 统计信息:")
        message_parts.append(f"• 总数: {total} 条")
        message_parts.append(f"• 已解锁: {total_unlocked} 条")
        message_parts.append(f"• 当前页: {page}")
        message_parts.append(f"• 每页: {page_size} 条")
        
        if items:
            message_parts.append(f"\n📝 泄露记录（显示前 {len(items)} 条）:")
            for i, item in enumerate(items[:10], 1):  # 最多显示10条
                url = item.get("url", "N/A")
                username = item.get("username", "N/A")
                unlocked = item.get("unlocked", False)
                is_email = item.get("is_email", False)
                
                # URL 可能被部分隐藏
                url_display = url[:50] + "..." if len(url) > 50 else url
                
                message_parts.append(f"\n{i}. {'🔓' if unlocked else '🔒'} {username} ({'邮箱' if is_email else '用户名'})")
                message_parts.append(f"   URL: {url_display}")
                
                if unlocked and item.get("password"):
                    password = item.get("password", "")
                    password_display = password[:20] + "..." if len(password) > 20 else password
                    message_parts.append(f"   密码: {password_display}")
        else:
            message_parts.append(f"\n✅ 未发现 {type_name}泄露记录")
        
        result_message = "\n".join(message_parts)
        
        if len(result_message) > 4000:
            result_message = result_message[:3900] + "\n\n... (内容过长，已截断)"
        
        return result_message
        
    except Exception as e:
        print(f"[格式化] 格式化泄露列表失败: {e}")
        return f"📋 原始响应:\n{json.dumps(api_result, indent=2, ensure_ascii=False)}"

def format_email_result(api_result: Dict[str, Any], email: str) -> str:
    """格式化邮箱查询结果"""
    if "error" in api_result:
        return f"❌ 查询失败\n\n邮箱: {email}\n错误: {api_result['error']}"
    
    try:
        items = api_result.get("items", [])
        total = api_result.get("total", 0)
        total_unlocked = api_result.get("total_unlocked", 0)
        
        message_parts = [f"📧 邮箱/用户名查询结果: {email}"]
        message_parts.append("=" * 40)
        message_parts.append(f"\n📊 统计信息:")
        message_parts.append(f"• 总数: {total} 条")
        message_parts.append(f"• 已解锁: {total_unlocked} 条")
        
        if items:
            message_parts.append(f"\n📝 泄露记录（显示前 {min(len(items), 10)} 条）:")
            for i, item in enumerate(items[:10], 1):
                url = item.get("url", "N/A")
                username = item.get("username", "N/A")
                unlocked = item.get("unlocked", False)
                
                url_display = url[:50] + "..." if len(url) > 50 else url
                message_parts.append(f"\n{i}. {'🔓' if unlocked else '🔒'} {url_display}")
                
                if unlocked and item.get("password"):
                    password = item.get("password", "")
                    password_display = password[:20] + "..." if len(password) > 20 else password
                    message_parts.append(f"   密码: {password_display}")
        else:
            message_parts.append(f"\n✅ 未发现泄露记录")
        
        result_message = "\n".join(message_parts)
        
        if len(result_message) > 4000:
            result_message = result_message[:3900] + "\n\n... (内容过长，已截断)"
        
        return result_message
        
    except Exception as e:
        print(f"[格式化] 格式化邮箱结果失败: {e}")
        return f"📋 邮箱: {email}\n\n原始响应:\n{json.dumps(api_result, indent=2, ensure_ascii=False)}"

def format_subdomains_result(api_result: Dict[str, Any], domain: str) -> str:
    """格式化子域名查询结果"""
    if "error" in api_result:
        return f"❌ 查询失败\n\n域名: {domain}\n错误: {api_result['error']}"
    
    try:
        items = api_result.get("items", [])
        total = api_result.get("total", 0)
        
        message_parts = [f"🌐 子域名查询结果: {domain}"]
        message_parts.append("=" * 40)
        message_parts.append(f"\n📊 统计信息:")
        message_parts.append(f"• 子域名总数: {total} 个")
        
        if items:
            message_parts.append(f"\n📝 子域名列表（显示前 {min(len(items), 20)} 个）:")
            for i, item in enumerate(items[:20], 1):
                subdomain = item.get("subdomain", "N/A")
                occurrences = item.get("occurrences", 0)
                message_parts.append(f"{i}. {subdomain} (出现 {occurrences} 次)")
        else:
            message_parts.append(f"\n✅ 未发现子域名")
        
        result_message = "\n".join(message_parts)
        
        if len(result_message) > 4000:
            result_message = result_message[:3900] + "\n\n... (内容过长，已截断)"
        
        return result_message
        
    except Exception as e:
        print(f"[格式化] 格式化子域名结果失败: {e}")
        return f"📋 域名: {domain}\n\n原始响应:\n{json.dumps(api_result, indent=2, ensure_ascii=False)}"

def create_domain_export(domain: str, leak_type: str) -> Dict[str, Any]:
    """
    创建域名泄露导出任务（CSV格式）
    
    API 端点: POST /search/domain/{domain}/{leak_type}/export
    
    Args:
        domain: 域名
        leak_type: 泄露类型 (employees/customers/third_parties)
        
    Returns:
        API 返回的 JSON 数据，包含 export_id
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/domain/{domain}/{leak_type}/export"
        params = {"format": "csv"}
        
        response = requests.post(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 403:
            return {"error": "需要付费计划才能使用导出功能"}
        elif response.status_code == 400:
            return {"error": "导出请求失败，请检查参数"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 创建导出任务失败: {e}")
        return {"error": f"创建导出任务失败: {str(e)}"}

def create_email_export(email: str) -> Dict[str, Any]:
    """
    创建邮箱泄露导出任务（CSV格式）
    
    API 端点: POST /search/email/export
    
    Args:
        email: 邮箱或用户名
        
    Returns:
        API 返回的 JSON 数据，包含 export_id
    """
    try:
        url = f"{LEAK_API_BASE_URL}/search/email/export"
        params = {"format": "csv"}
        payload = {"email": email}
        
        response = requests.post(
            url,
            params=params,
            json=payload,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        elif response.status_code == 403:
            return {"error": "需要付费计划才能使用导出功能"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 创建邮箱导出任务失败: {e}")
        return {"error": f"创建导出任务失败: {str(e)}"}

def get_exports_list(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    获取导出任务列表
    
    API 端点: GET /exports
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        API 返回的导出任务列表
    """
    try:
        url = f"{LEAK_API_BASE_URL}/exports"
        params = {
            "page": page,
            "page_size": page_size
        }
        
        response = requests.get(
            url,
            params=params,
            headers=LEAK_API_HEADERS,
            timeout=30
        )
        
        if response.status_code == 401:
            return {"error": "API 认证失败，请检查 API Key"}
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"[API] 获取导出列表失败: {e}")
        return {"error": f"获取导出列表失败: {str(e)}"}

def get_export_status(export_id: int) -> Dict[str, Any]:
    """
    获取导出任务状态
    
    通过 /exports 端点获取特定导出任务的状态
    
    Args:
        export_id: 导出任务 ID
        
    Returns:
        导出任务状态信息
    """
    try:
        # 获取导出列表，查找指定的 export_id
        exports_result = get_exports_list(page=1, page_size=100)
        
        if "error" in exports_result:
            return exports_result
        
        items = exports_result.get("items", [])
        for item in items:
            if item.get("id") == export_id:
                return item
        
        return {"error": f"未找到导出任务 ID: {export_id}"}
        
    except Exception as e:
        print(f"[API] 获取导出状态失败: {e}")
        return {"error": f"获取导出状态失败: {str(e)}"}

def download_export_file(export_id: int, download_path: str = None) -> Optional[str]:
    """
    下载导出文件
    
    尝试多种方式下载文件：
    1. 从导出状态中获取 download_url
    2. 尝试通过 /exports/{export_id}/download 端点下载
    3. 尝试通过 /exports/{export_id}/file 端点下载
    
    Args:
        export_id: 导出任务 ID
        download_path: 下载保存路径（可选）
        
    Returns:
        下载的文件路径，如果失败返回 None
    """
    try:
        # 先检查导出状态
        status = get_export_status(export_id)
        
        # 打印完整状态用于调试
        print(f"[下载调试] 导出状态详情: {json.dumps(status, ensure_ascii=False)}")
        
        if "error" in status:
            print(f"[下载] {status['error']}")
            return None
        
        export_status = status.get("status", "").upper()
        
        if export_status != "COMPLETED":
            print(f"[下载] 导出任务尚未完成，状态: {export_status}")
            return None
        
        filename = status.get("filename", f"export_{export_id}.csv")
        
        if download_path is None:
            # 创建临时目录
            temp_dir = "temp_exports"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            download_path = os.path.join(temp_dir, filename)
        
        # 方法1: 尝试从状态中获取 download_url
        download_url = status.get("download_url") or status.get("url")
        
        if download_url:
            try:
                response = requests.get(download_url, headers=LEAK_API_HEADERS, timeout=60, stream=True)
                response.raise_for_status()
                
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"[下载] 文件已下载: {download_path}")
                return download_path
            except Exception as e:
                print(f"[下载] 方法1失败: {e}")
        
        # 方法2: 尝试通过 /exports/{export_id}/download 端点
        try:
            download_url = f"{LEAK_API_BASE_URL}/exports/{export_id}/download"
            response = requests.get(download_url, headers=LEAK_API_HEADERS, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"[下载] 文件已下载: {download_path}")
            return download_path
        except Exception as e:
            print(f"[下载] 方法2失败: {e}")
        
        # 方法3: 尝试通过 /exports/{export_id}/file 端点
        try:
            download_url = f"{LEAK_API_BASE_URL}/exports/{export_id}/file"
            response = requests.get(download_url, headers=LEAK_API_HEADERS, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"[下载] 文件已下载: {download_path}")
            return download_path
        except Exception as e:
            print(f"[下载] 方法3失败: {e}")
        
        # 如果所有方法都失败，返回 None
        print(f"[下载] 所有下载方法都失败，无法下载文件")
        return None
        
    except Exception as e:
        print(f"[下载] 下载文件失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def wait_for_export_completion(export_id: int, max_wait_time: int = 300, check_interval: int = 5) -> Dict[str, Any]:
    """
    等待导出任务完成
    
    Args:
        export_id: 导出任务 ID
        max_wait_time: 最大等待时间（秒）
        check_interval: 检查间隔（秒）
        
    Returns:
        导出任务状态
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        status = get_export_status(export_id)
        
        if "error" in status:
            return status
        
        export_status = status.get("status", "").upper()
        
        if export_status == "COMPLETED":
            return status
        elif export_status in ["FAILED", "ERROR"]:
            return {"error": f"导出任务失败，状态: {export_status}"}
        
        time.sleep(check_interval)
    
    return {"error": f"等待超时，导出任务可能仍在处理中"}

def format_urls_result(api_result: Dict[str, Any], domain: str) -> str:
    """格式化 URL 查询结果"""
    if "error" in api_result:
        return f"❌ 查询失败\n\n域名: {domain}\n错误: {api_result['error']}"
    
    try:
        items = api_result.get("items", [])
        total = api_result.get("total", 0)
        
        message_parts = [f"🔗 URL 查询结果: {domain}"]
        message_parts.append("=" * 40)
        message_parts.append(f"\n📊 统计信息:")
        message_parts.append(f"• URL 总数: {total} 个")
        
        if items:
            message_parts.append(f"\n📝 URL 列表（显示前 {min(len(items), 20)} 个）:")
            for i, item in enumerate(items[:20], 1):
                url = item.get("url", "N/A")
                occurrences = item.get("occurrences", 0)
                url_display = url[:60] + "..." if len(url) > 60 else url
                message_parts.append(f"{i}. {url_display} (出现 {occurrences} 次)")
        else:
            message_parts.append(f"\n✅ 未发现 URL")
        
        result_message = "\n".join(message_parts)
        
        if len(result_message) > 4000:
            result_message = result_message[:3900] + "\n\n... (内容过长，已截断)"
        
        return result_message
        
    except Exception as e:
        print(f"[格式化] 格式化 URL 结果失败: {e}")
        return f"📋 域名: {domain}\n\n原始响应:\n{json.dumps(api_result, indent=2, ensure_ascii=False)}"

def handle_message(message: Dict[str, Any]) -> None:
    """处理接收到的消息"""
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user = message.get("from", {})
    user_name = user.get("first_name", "用户")
    user_id = user.get("id", 0)
    
    print(f"[消息] 用户 {user_name} ({user_id}): {text}")
    
    # 移除 @bot_username 部分，以便在群组中处理命令
    if "@" in text:
        # 获取机器人用户名（这里简单处理，假设是命令后的第一个 @）
        # 更好的方式是在启动时获取 getMe 信息
        text = re.sub(r'@\w+', '', text).strip()
        print(f"[处理] 去除 @ 后命令: {text}")

    # 处理 /start 命令
    if text == "/start":
        welcome_message = (
            f"你好 {user_name}！我是lysir_bot账密泄露查询机器人🔍\n\n"
            "📋 使用说明：\n"
            "• 直接发送域名即可查询账密泄露情况\n"
            "• 例如：example.com 或 www.example.com\n\n"
            "💡 提示：\n"
            "• 我会自动处理域名格式，支持带 http:// 或 www. 的域名\n"
            "• 查询结果包括员工、第三方和客户的泄露统计\n"
            "• 完整版本会显示密码强度统计信息\n\n"
            "📖 输入 /help 查看详细帮助"
        )
        send_message(chat_id, welcome_message)
        print(f"[回复] 发送欢迎消息给用户 {user_name}")
    
    # 处理 /help 命令
    elif text == "/help":
        help_message = (
            "📖 lysir_bot 账密泄露查询机器人帮助\n\n"
            "🔍 查询方式：\n\n"
            "1️⃣ 域名泄露报告（默认）\n"
            "直接发送域名即可查询，例如：\n"
            "• example.com\n"
            "• www.example.com\n\n"
            "2️⃣ 查询详细泄露列表\n"
            "• /employees <域名> - 查询员工泄露列表\n"
            "• /customers <域名> - 查询客户泄露列表\n"
            "• /thirdparties <域名> - 查询第三方泄露列表\n\n"
            "3️⃣ 邮箱/用户名查询\n"
            "• /email <邮箱或用户名> - 查询邮箱泄露\n"
            "例如：/email user@example.com\n\n"
            "4️⃣ 子域名查询\n"
            "• /subdomains <域名> - 查询子域名列表\n\n"
            "5️⃣ URL 查询\n"
            "• /urls <域名> - 查询相关 URL 列表\n\n"
            "6️⃣ CSV 导出功能（重要）\n"
            "• /export employees <域名> - 导出员工泄露 CSV\n"
            "• /export customers <域名> - 导出客户泄露 CSV\n"
            "• /export thirdparties <域名> - 导出第三方泄露 CSV\n"
            "• /export all <域名> - 导出全部（员工+客户+第三方）\n"
            "• /export email <邮箱> - 导出邮箱泄露 CSV\n"
            "• /exports - 查看所有导出任务\n\n"
            "⚙️ 命令列表：\n"
            "/start - 开始使用\n"
            "/help - 显示帮助信息\n\n"
            "💡 提示：\n"
            "• 导出任务完成后会自动发送 CSV 文件\n"
            "• 查询结果可能包含敏感信息，请谨慎使用"
        )
        send_message(chat_id, help_message)
        print(f"[回复] 发送帮助信息给用户 {user_name}")
    
    # 处理 /employees 命令
    elif text.startswith("/employees "):
        domain = text.replace("/employees ", "").strip()
        normalized_domain = normalize_domain(domain)
        
        if not is_valid_domain(normalized_domain):
            send_message(chat_id, f"❌ 域名格式无效: {domain}")
            return
        
        send_message(chat_id, f"🔍 正在查询员工泄露: {normalized_domain}\n请稍候...")
        result = query_domain_leaks(normalized_domain, "employees")
        formatted = format_leaks_list(result, "employees", normalized_domain)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询员工泄露: {normalized_domain}")
    
    # 处理 /customers 命令
    elif text.startswith("/customers "):
        domain = text.replace("/customers ", "").strip()
        normalized_domain = normalize_domain(domain)
        
        if not is_valid_domain(normalized_domain):
            send_message(chat_id, f"❌ 域名格式无效: {domain}")
            return
        
        send_message(chat_id, f"🔍 正在查询客户泄露: {normalized_domain}\n请稍候...")
        result = query_domain_leaks(normalized_domain, "customers")
        formatted = format_leaks_list(result, "customers", normalized_domain)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询客户泄露: {normalized_domain}")
    
    # 处理 /thirdparties 命令
    elif text.startswith("/thirdparties ") or text.startswith("/third_parties "):
        domain = text.replace("/thirdparties ", "").replace("/third_parties ", "").strip()
        normalized_domain = normalize_domain(domain)
        
        if not is_valid_domain(normalized_domain):
            send_message(chat_id, f"❌ 域名格式无效: {domain}")
            return
        
        send_message(chat_id, f"🔍 正在查询第三方泄露: {normalized_domain}\n请稍候...")
        result = query_domain_leaks(normalized_domain, "third_parties")
        formatted = format_leaks_list(result, "third_parties", normalized_domain)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询第三方泄露: {normalized_domain}")
    
    # 处理 /email 命令
    elif text.startswith("/email "):
        email = text.replace("/email ", "").strip()
        
        if not email:
            send_message(chat_id, "❌ 请输入邮箱或用户名\n例如：/email user@example.com")
            return
        
        send_message(chat_id, f"🔍 正在查询邮箱泄露: {email}\n请稍候...")
        result = query_email_leaks(email)
        formatted = format_email_result(result, email)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询邮箱: {email}")
    
    # 处理 /subdomains 命令
    elif text.startswith("/subdomains "):
        domain = text.replace("/subdomains ", "").strip()
        normalized_domain = normalize_domain(domain)
        
        if not is_valid_domain(normalized_domain):
            send_message(chat_id, f"❌ 域名格式无效: {domain}")
            return
        
        send_message(chat_id, f"🔍 正在查询子域名: {normalized_domain}\n请稍候...")
        result = query_domain_subdomains(normalized_domain)
        formatted = format_subdomains_result(result, normalized_domain)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询子域名: {normalized_domain}")
    
    # 处理 /urls 命令
    elif text.startswith("/urls "):
        domain = text.replace("/urls ", "").strip()
        normalized_domain = normalize_domain(domain)
        
        if not is_valid_domain(normalized_domain):
            send_message(chat_id, f"❌ 域名格式无效: {domain}")
            return
        
        send_message(chat_id, f"🔍 正在查询 URL: {normalized_domain}\n请稍候...")
        result = query_domain_urls(normalized_domain)
        formatted = format_urls_result(result, normalized_domain)
        send_message(chat_id, formatted)
        print(f"[查询] 用户 {user_name} 查询 URL: {normalized_domain}")
    
    # 处理 /export 命令 - 导出域名泄露为 CSV
    elif text.startswith("/export "):
        parts = text.replace("/export ", "").strip().split()
        if len(parts) < 2:
            send_message(chat_id, 
                "❌ 命令格式错误\n\n"
                "正确格式：\n"
                "/export <类型> <域名或邮箱>\n\n"
                "类型：\n"
                "• employees - 员工泄露\n"
                "• customers - 客户泄露\n"
                "• thirdparties - 第三方泄露\n"
                "• all - 导出全部（员工+客户+第三方）\n"
                "• email - 邮箱泄露\n\n"
                "示例：\n"
                "/export employees example.com\n"
                "/export all example.com\n"
                "/export email user@example.com"
            )
            return
        
        export_type = parts[0].lower()
        target = " ".join(parts[1:])
        
        # 处理 /export all 命令 - 导出全部泄露类型
        if export_type == "all":
            normalized_domain = normalize_domain(target)
            
            if not is_valid_domain(normalized_domain):
                send_message(chat_id, f"❌ 域名格式无效: {target}")
                return
            
            send_message(chat_id, 
                f"📥 正在处理全部泄露导出: {normalized_domain}\n\n"
                f"1. 正在尝试自动解锁数据...\n"
                f"2. 正在获取并生成 CSV 文件...\n\n"
                f"请稍候，这可能需要几分钟..."
            )
            
            leak_types = [
                ("employees", "员工"),
                ("customers", "客户"),
                ("third_parties", "第三方")
            ]
            
            completed_count = 0
            
            for leak_type, type_name in leak_types:
                # 1. 解锁
                print(f"[解锁] 正在解锁 {type_name} 数据: {normalized_domain}")
                unlock_result = unlock_domain_leaks(normalized_domain, leak_type, max_items=10000)
                
                unlocked_count = 0
                if isinstance(unlock_result, list):
                    unlocked_count = len(unlock_result)
                    print(f"[解锁] 成功解锁 {unlocked_count} 条 {type_name} 数据")
                elif isinstance(unlock_result, dict) and "error" in unlock_result:
                    print(f"[解锁] {type_name} 解锁失败: {unlock_result['error']}")
                
                # 2. Fetch all data
                items = fetch_all_domain_leaks(normalized_domain, leak_type)
                
                if items:
                    # 3. Create CSV
                    file_path = create_csv_file(items, f"{normalized_domain}_{leak_type}")
                    if file_path:
                        caption = (
                            f"📥 CSV 导出文件\n\n"
                            f"域名: {normalized_domain}\n"
                            f"类型: {type_name}\n"
                            f"记录数: {len(items)}\n"
                            f"本次解锁: {unlocked_count} 条"
                        )
                        if send_document(chat_id, file_path, caption):
                            completed_count += 1
                            try:
                                os.remove(file_path)
                            except:
                                pass
                else:
                    print(f"[导出] {type_name} 没有数据")
            
            if completed_count > 0:
                send_message(chat_id, f"✅ 已发送 {completed_count} 个 CSV 文件")
            else:
                send_message(chat_id, "⚠️ 未找到任何数据或导出失败")
            return
        
        if export_type == "email":
            # 导出邮箱泄露
            # send_message(chat_id, f"📥 正在处理邮箱导出: {target}\n正在解锁并获取数据，请稍候...")
            send_message(chat_id, f"📥 已接收邮箱导出任务: {target}\n请稍候...")
            
            # 1. 解锁
            unlock_email_leaks(target)
            
            # 2. Fetch
            items = fetch_all_email_leaks(target)
            
            if items:
                file_path = create_csv_file(items, f"email_{target}")
                if file_path:
                    caption = f"📥 CSV 导出文件\n\n邮箱: {target}\n记录数: {len(items)}"
                    if send_document(chat_id, file_path, caption):
                        send_message(chat_id, f"✅ CSV 文件已发送")
                        try:
                            os.remove(file_path)
                        except:
                            pass
                    else:
                        send_message(chat_id, f"❌ 发送文件失败")
            else:
                send_message(chat_id, "⚠️ 未找到相关数据")
        
        elif export_type in ["employees", "customers", "thirdparties", "third_parties"]:
            # 导出域名泄露
            normalized_domain = normalize_domain(target)
            
            if not is_valid_domain(normalized_domain):
                send_message(chat_id, f"❌ 域名格式无效: {target}")
                return
            
            leak_type = export_type if export_type != "thirdparties" else "third_parties"
            type_names = {
                "employees": "员工",
                "customers": "客户",
                "third_parties": "第三方"
            }
            type_name = type_names.get(leak_type, leak_type)
            
            send_message(chat_id, f"📥 正在处理{type_name}泄露导出: {normalized_domain}\n正在解锁并获取数据，请稍候...")
            
            # 1. 解锁
            unlock_domain_leaks(normalized_domain, leak_type, max_items=10000)
            
            # 2. Fetch
            items = fetch_all_domain_leaks(normalized_domain, leak_type)
            
            if items:
                file_path = create_csv_file(items, f"{normalized_domain}_{leak_type}")
                if file_path:
                    caption = f"📥 CSV 导出文件\n\n域名: {normalized_domain}\n类型: {type_name}\n记录数: {len(items)}"
                    if send_document(chat_id, file_path, caption):
                        send_message(chat_id, f"✅ CSV 文件已发送")
                        try:
                            os.remove(file_path)
                        except:
                            pass
                    else:
                        send_message(chat_id, f"❌ 发送文件失败")
            else:
                send_message(chat_id, "⚠️ 未找到相关数据")
        elif export_type == "all":
            # all 类型已经在上面处理了，这里不应该到达
            pass
        else:
            send_message(chat_id, 
                "❌ 无效的导出类型\n\n"
                "支持的类型：\n"
                "• employees - 员工泄露\n"
                "• customers - 客户泄露\n"
                "• thirdparties - 第三方泄露\n"
                "• all - 导出全部（员工+客户+第三方）\n"
                "• email - 邮箱泄露"
            )
    
    # 处理 /exports 命令 - 查看导出任务列表
    elif text == "/exports":
        send_message(chat_id, "📋 正在获取导出任务列表...")
        result = get_exports_list(page=1, page_size=10)
        
        if "error" in result:
            send_message(chat_id, f"❌ 获取导出列表失败\n\n错误: {result['error']}")
        else:
            items = result.get("items", [])
            total = result.get("total", 0)
            
            if not items:
                send_message(chat_id, "📋 暂无导出任务")
            else:
                message_parts = [f"📋 导出任务列表（共 {total} 个）\n", "=" * 40]
                
                for i, item in enumerate(items[:10], 1):
                    export_id = item.get("id")
                    filename = item.get("filename", "N/A")
                    status = item.get("status", "UNKNOWN")
                    timestamp = item.get("timestamp", "")
                    finished_at = item.get("finished_at")
                    
                    status_emoji = {
                        "COMPLETED": "✅",
                        "PENDING": "⏳",
                        "IN_PROGRESS": "🔄",
                        "FAILED": "❌"
                    }.get(status.upper(), "❓")
                    
                    message_parts.append(f"\n{i}. {status_emoji} {filename}")
                    message_parts.append(f"   ID: {export_id}")
                    message_parts.append(f"   状态: {status}")
                    if finished_at:
                        message_parts.append(f"   完成时间: {finished_at}")
                
                if total > 10:
                    message_parts.append(f"\n... 还有 {total - 10} 个任务未显示")
                
                send_message(chat_id, "\n".join(message_parts))
                print(f"[查询] 用户 {user_name} 查看导出列表")
    
    # 处理域名查询（普通文本消息且不是命令）
    elif text and not text.startswith("/"):
        # 规范化域名
        normalized_domain = normalize_domain(text)
        
        # 验证域名格式
        if not is_valid_domain(normalized_domain):
            error_message = (
                f"❌ 域名格式无效\n\n"
                f"你输入的: {text}\n\n"
                "请输入有效的域名，例如：\n"
                "• example.com\n"
                "• www.example.com"
            )
            send_message(chat_id, error_message)
            print(f"[回复] 域名格式错误: {text}")
            return
        
        # 发送查询中的提示
        send_message(chat_id, f"🔍 正在查询域名: {normalized_domain}\n请稍候...")
        print(f"[查询] 用户 {user_name} 查询域名: {normalized_domain}")
        
        # 调用 API 查询
        api_result = query_leak_api(normalized_domain)
        
        # 格式化并发送结果
        formatted_result = format_api_result(api_result, normalized_domain)
        send_message(chat_id, formatted_result)
        print(f"[回复] 发送查询结果给用户 {user_name}")

def main():
    """主函数"""
    global last_update_id
    
    print("=" * 60)
    print("Telegram 机器人启动中...")
    print("=" * 60)
    print(f"Bot Token: {TOKEN[:10]}...")
    print(f"Telegram API 地址: {API_BASE_URL}")
    print(f"API 地址: {LEAK_API_BASE_URL}")
    print(f"API Key: {LEAK_API_KEY[:5]}..." if LEAK_API_KEY else "Not Set")
    print("=" * 60)
    
    # 清除 Webhook
    delete_webhook()

    # 测试连接
    print("正在测试 Telegram API 连接...")
    # test_result = get_updates(timeout=1, offset=0)
    # 使用 offset=-1 获取最新消息（不确认之前的）
    test_result = get_updates(timeout=1)
    
    if not test_result.get("ok"):
        print("❌ 无法连接到 Telegram API，请检查：")
        print("   1. Token 是否正确")
        print("   2. 网络连接是否正常")
        print("   3. 是否能够访问 api.telegram.org")
        return
    
    print("✓ 成功连接到 Telegram API")
    print("✓ 机器人已启动，等待消息...")
    print("=" * 60)
    print("按 Ctrl+C 停止机器人")
    print("=" * 60)
    print()
    
    # 打印当前代理设置
    import urllib.request
    proxies = urllib.request.getproxies()
    print(f"当前系统代理设置: {proxies}")
    
    try:
        loop_count = 0
        while True:
            loop_count += 1
            if loop_count % 10 == 0:  # 每10次循环（约5秒）打印一次心跳
                print(f"[心跳] 正在运行中... (Loop {loop_count})", flush=True)
                
            # 获取更新
            # print(f"正在获取更新 (offset={last_update_id + 1})...")
            
            # 如果是第一次循环且 last_update_id 为 0，不传 offset 以获取默认未确认消息
            if last_update_id == 0:
                result = get_updates(timeout=5)
            else:
                result = get_updates(timeout=5, offset=last_update_id + 1)
            
            if not result.get("ok"):
                print(f"获取更新失败: {result}")
                time.sleep(5)
                continue
            
            updates = result.get("result", [])
            if updates:
                print(f"收到 {len(updates)} 条新消息")
            
            for update in updates:
                update_id = update.get("update_id")
                last_update_id = max(last_update_id, update_id)
                
                # 处理消息
                if "message" in update:
                    message = update["message"]
                    if "text" in message:
                        handle_message(message)
            
            # 短暂休眠，避免频繁请求
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\n收到中断信号，正在关闭机器人...")
        print("机器人已停止")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

