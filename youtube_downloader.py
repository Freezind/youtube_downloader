import os
import re
import logging
from pydantic import Field

from proconfig.widgets.base import WIDGETS, BaseWidget

from apify_client import ApifyClient

@WIDGETS.register_module()
class YouTubeDownloaderWidget(BaseWidget):
    """
    YouTube视频下载器Widget，使用Apify API获取YouTube视频下载链接。
    需要设置环境变量APIFY_API_KEY。
    """
    CATEGORY = "Custom Widgets/Media Tools"
    NAME = "YouTube Video Downloader"

    class InputsSchema(BaseWidget.InputsSchema):
        url: str = Field("https://www.youtube.com/watch?v=dQw4w9WgXcQ", description="YouTube视频URL")
        resolution: str = Field("360", description="视频分辨率 (720, 480, 360)")
        use_residential_proxy: bool = Field(False, description="是否使用住宅代理")
        proxy_country: str = Field("US", description="代理服务器国家/地区代码")

    class OutputsSchema(BaseWidget.OutputsSchema):
        success: bool = Field(description="是否成功获取下载链接")
        message: str = Field(description="状态消息")
        video_title: str = Field("", description="视频标题")
        mp4_url: str = Field("", description="MP4下载链接")
            
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
                    "video_title": "",
                    "mp4_url": ""
                }
            
            # 验证输入参数
            try:
                self._validate_url(config.url)
                self._validate_resolution(config.resolution)
            except ValueError as e:
                return {
                    "success": False,
                    "message": str(e),
                    "video_title": "",
                    "mp4_url": ""
                }

            # 创建Apify客户端
            client = ApifyClient(apify_api_key)

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
                    "video_title": "",
                    "mp4_url": ""
                }
            
            video_info = items[0]
            
            # 提取视频信息
            title = video_info.get("title", "未知标题")
            
            # 下载链接
            download_url = video_info.get("downloadUrl", "")
            
            if not download_url:
                return {
                    "success": False,
                    "message": "未找到下载链接",
                    "video_title": title,
                    "mp4_url": ""
                }
            
            return {
                "success": True,
                "message": f"成功获取视频下载链接: {title}",
                "video_title": title,
                "mp4_url": download_url
            }

        except Exception as e:
            # 记录错误并处理
            logging.error(f"获取下载链接失败: {repr(e)}")
            return {
                "success": False,
                "message": f"获取下载链接失败: {repr(e)}",
                "video_title": "",
                "mp4_url": ""
            }


if __name__ == "__main__":
    # 必须在运行前设置环境变量
    os.environ["APIFY_API_KEY"] = ""
    
    widget = YouTubeDownloaderWidget()
    test_config = {
        "url": "https://www.youtube.com/watch?v=hz6oys4Eem4",
        "resolution": "360",
        "use_residential_proxy": True,
        "proxy_country": "US"
    }

    result = widget({}, test_config)
    print(result)
