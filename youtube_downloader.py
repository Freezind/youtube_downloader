import os
import re
import logging
import requests
from pydantic import Field

from proconfig.widgets.base import WIDGETS, BaseWidget

from apify_client import ApifyClient

@WIDGETS.register_module()
class YouTubeDownloaderWidget(BaseWidget):
    """
    YouTube视频下载器Widget，使用Apify API获取YouTube视频下载链接。
    需要设置环境变量APIFY_API_KEY。
    
    增强功能:
    1. 使用key_value_store缓存下载链接
    2. 检查缓存的链接是否有效，若无效则重新获取
    """
    CATEGORY = "Custom Widgets/Media Tools"
    NAME = "YouTube Video Downloader"

    class InputsSchema(BaseWidget.InputsSchema):
        url: str = Field("https://www.youtube.com/watch?v=dQw4w9WgXcQ", description="YouTube视频URL")
        resolution: str = Field("360", description="视频分辨率 (720, 480, 360)")
        use_residential_proxy: bool = Field(False, description="是否使用住宅代理")
        proxy_country: str = Field("US", description="代理服务器国家/地区代码")
        force_refresh: bool = Field(False, description="强制刷新缓存")

    class OutputsSchema(BaseWidget.OutputsSchema):
        success: bool = Field(description="是否成功获取下载链接")
        message: str = Field(description="状态消息")
        mp4_url: str = Field("", description="MP4下载链接")
        cached: bool = Field(False, description="是否使用了缓存")
            
    def _validate_url(self, url):
        """验证YouTube URL格式"""
        if not url:
            raise ValueError("请提供YouTube视频URL")

        # 简单验证YouTube URL格式
        youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        match = re.match(youtube_regex, url)
        if not match:
            raise ValueError("无效的YouTube URL")
        return True
        
    def _validate_resolution(self, resolution):
        """验证分辨率格式"""
        valid_resolutions = ["2160", "1440", "1080", "720", "480", "360", "240", "144"]
        if resolution not in valid_resolutions:
            raise ValueError(f"分辨率必须是以下之一: {', '.join(valid_resolutions)}")
        return True
    
    def _get_video_id(self, url):
        """从YouTube URL中提取视频ID"""
        patterns = [
            r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _get_or_create_store(self, client):
        """获取或创建key_value_store"""
        store = client.key_value_stores().get_or_create(name="youtube-downloader")
        return store["id"]
    
    def _get_link_from_store(self, client, store_id, youtube_url, resolution):
        """从store中获取链接映射"""
        MAP_KEY = f"youtube_link_map_{resolution}"
        
        try:
            record = client.key_value_store(store_id).get_record(MAP_KEY)
            link_map = record["value"] if record and "value" in record else {}
            
            return link_map.get(youtube_url)
        except Exception as e:
            logging.error(f"从KV存储获取链接失败: {repr(e)}")
            return None
    
    def _save_link_to_store(self, client, store_id, youtube_url, download_url, resolution):
        """保存链接映射到store"""
        MAP_KEY = f"youtube_link_map_{resolution}"
        
        try:
            # 获取原有数据（如果没有则用空dict）
            record = client.key_value_store(store_id).get_record(MAP_KEY)
            link_map = record["value"] if record and "value" in record else {}
            
            # 更新字典
            link_map[youtube_url] = download_url
            
            # 存回去
            client.key_value_store(store_id).set_record(MAP_KEY, link_map)
            logging.info(f"成功保存链接映射: {youtube_url} -> {download_url}")
            return True
        except Exception as e:
            logging.error(f"保存链接映射失败: {repr(e)}")
            return False
    
    def _is_url_valid(self, url):
        """检查URL是否有效"""
        if not url:
            return False
            
        try:
            # 发送HEAD请求检查URL是否有效
            response = requests.head(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"URL有效性检查失败: {repr(e)}")
            return False

    def execute(self, environ, config):
        """
        执行YouTube视频下载链接获取

        Args:
            environ: 环境变量
            config: 配置参数，包含url，resolution等

        Returns:
            包含下载链接的字典
        """
        try:
            # 从环境变量获取Apify API密钥
            apify_api_key = os.environ.get("APIFY_API_KEY")
            
            # 如果环境变量中没有API密钥，返回错误
            if not apify_api_key:
                return {
                    "success": False,
                    "message": "缺少APIFY_API_KEY环境变量，请设置后再试",
                    "mp4_url": "",
                    "cached": False
                }
            
            # 验证输入参数
            try:
                self._validate_url(config.url)
                self._validate_resolution(config.resolution)
            except ValueError as e:
                return {
                    "success": False,
                    "message": str(e),
                    "mp4_url": "",
                    "cached": False
                }

            # 创建Apify客户端
            client = ApifyClient(apify_api_key)
            
            # 获取或创建KV存储
            store_id = self._get_or_create_store(client)
            
            # 获取视频ID (用于日志和调试)
            video_id = self._get_video_id(config.url)
            
            # 先尝试从缓存获取下载链接
            if not config.force_refresh:
                cached_url = self._get_link_from_store(client, store_id, config.url, config.resolution)
                
                if cached_url:
                    # 检查链接是否仍然有效
                    if self._is_url_valid(cached_url):
                        logging.info(f"使用缓存的下载链接: {cached_url}")
                        
                        return {
                            "success": True,
                            "message": "成功获取缓存的视频下载链接",
                            "mp4_url": cached_url,
                            "cached": True
                        }
                    else:
                        logging.info(f"缓存的下载链接已失效，重新获取: {cached_url}")
            
            # 配置使用新的Actor
            actor_id = "y1IMcEPawMQPafm02"
            
            # 配置代理设置
            proxy_configuration = {
                "useApifyProxy": True
            }
            
            # 如果用户选择使用住宅代理，则添加相应配置
            if config.use_residential_proxy:
                proxy_configuration["apifyProxyGroups"] = ["RESIDENTIAL"]
                if config.proxy_country:
                    proxy_configuration["apifyProxyCountry"] = config.proxy_country
            
            # 准备Actor输入参数
            run_input = {
                "startUrls": [
                     config.url
                ],
                "quality": config.resolution,
                "useFfmpeg": False,
                "includeFailedVideos": False,
                "proxy": proxy_configuration,
            }
            
            # 运行Actor并等待完成
            run = client.actor(actor_id).call(run_input=run_input)
            
            # 获取结果
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                return {
                    "success": False,
                    "message": "无法获取视频信息",
                    "mp4_url": "",
                    "cached": False
                }
            
            video_info = items[0]
            
            # 下载链接
            download_url = video_info.get("downloadUrl", "")
            
            if not download_url:
                return {
                    "success": False,
                    "message": "未找到下载链接",
                    "mp4_url": "",
                    "cached": False
                }
            
            # 将链接保存到KV存储
            self._save_link_to_store(client, store_id, config.url, download_url, config.resolution)
            
            return {
                "success": True,
                "message": "成功获取视频下载链接",
                "mp4_url": download_url,
                "cached": False
            }

        except Exception as e:
            # 记录错误并处理
            logging.error(f"获取下载链接失败: {repr(e)}")
            return {
                "success": False,
                "message": f"获取下载链接失败: {repr(e)}",
                "mp4_url": "",
                "cached": False
            }


if __name__ == "__main__":
    # 必须在运行前设置环境变量
    os.environ["APIFY_API_KEY"] = ""
    
    widget = YouTubeDownloaderWidget()
    test_config = {
        "url": "https://www.youtube.com/watch?v=hz6oys4Eem4",
        "resolution": "360",
        "use_residential_proxy": True,
        "proxy_country": "US",
        "force_refresh": False
    }

    result = widget({}, test_config)
    print(result)
