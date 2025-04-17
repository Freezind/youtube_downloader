"""
YouTubeDownloaderWidget 测试脚本
用于测试 YouTube 下载器 Widget 功能
"""
import os
import logging
import time
from pathlib import Path
from easydict import EasyDict
from youtube_downloader import YouTubeDownloaderWidget

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入我们的widget
try:
    from youtube_downloader import YouTubeDownloaderWidget
except ImportError:
    logger.error("无法导入YouTubeDownloaderWidget，请确保已安装所需依赖")
    raise

def test_youtube_downloader():
    """测试YouTube下载器Widget"""
    
    # 获取Apify API密钥
    apify_api_key = os.environ.get("APIFY_API_KEY")
    if not apify_api_key:
        print("错误: 未设置APIFY_API_KEY环境变量")
        return
    
    # 实例化Widget
    widget = YouTubeDownloaderWidget()
    
    # 测试用例
    test_cases = [
        {
            "name": "测试1: 基本下载 (强制刷新)",
            "config": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
                "resolution": "360",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": True
            }
        },
        {
            "name": "测试2: 缓存下载 (使用缓存)",
            "config": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
                "resolution": "360",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": False
            }
        },
        {
            "name": "测试3: 不同分辨率 (强制刷新)",
            "config": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
                "resolution": "720",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": True
            }
        },
        {
            "name": "测试4: 不同分辨率 (使用缓存)",
            "config": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
                "resolution": "720",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": False
            }
        },
        {
            "name": "测试5: 短视频 (强制刷新)",
            "config": {
                "url": "https://www.youtube.com/shorts/bOUOSn9MULw",  # YouTube Shorts
                "resolution": "360",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": True
            }
        },
        {
            "name": "测试6: 错误的URL",
            "config": {
                "url": "https://www.youtube.com/invalid",
                "resolution": "360",
                "use_residential_proxy": False,
                "proxy_country": "US",
                "force_refresh": False
            }
        }
    ]
    
    # 运行测试用例
    for test in test_cases:
        print(f"\n开始运行 {test['name']}")
        start_time = time.time()
        result = widget({}, test["config"])
        end_time = time.time()
        
        print(f"结果: {'成功' if result['success'] else '失败'}")
        print(f"信息: {result['message']}")
        print(f"使用缓存: {'是' if result['cached'] else '否'}")
        if result['success']:
            print(f"下载链接: {result['mp4_url'][:60]}...")
        print(f"耗时: {end_time - start_time:.2f}秒")
        
        # 在测试之间暂停，避免过快请求
        if test != test_cases[-1]:
            print("等待5秒...")
            time.sleep(5)

def test_url_validation():
    """测试URL验证功能"""
    widget = YouTubeDownloaderWidget()
    
    test_urls = [
        # 有效的URL
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/bOUOSn9MULw",
        
        # 无效的URL
        "https://www.youtobe.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watchv=dQw4w9WgXcQ",
        "https://www.youtube.com/",
        "https://www.google.com",
        ""
    ]
    
    print("\n测试URL验证功能")
    for url in test_urls:
        try:
            is_valid = widget._validate_url(url)
            video_id = widget._get_video_id(url)
            print(f"URL: {url}")
            print(f"有效: {is_valid}")
            print(f"视频ID: {video_id}")
        except ValueError as e:
            print(f"URL: {url}")
            print(f"错误: {str(e)}")
        print("---")

if __name__ == "__main__":
    # 设置API密钥
    os.environ["APIFY_API_KEY"] = ""  # 请在此填入你的Apify API密钥
    
    # 运行测试
    test_youtube_downloader()
    test_url_validation() 