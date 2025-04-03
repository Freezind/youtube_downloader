import os
import re
import logging
from pathlib import Path
from typing import Any, Optional
from pydantic import Field
import requests
from datetime import datetime
from moviepy.editor import VideoFileClip

from proconfig.widgets.base import WIDGETS, BaseWidget
from proconfig.utils.misc import upload_file_to_myshell

from apify_client import ApifyClient

@WIDGETS.register_module()
class YouTubeDownloaderWidget(BaseWidget):
    """
    YouTube视频下载器Widget，使用Apify API下载视频，并支持转换为MP3。
    需要设置环境变量APIFY_API_KEY。
    """
    CATEGORY = "Custom Widgets/Media Tools"
    NAME = "YouTube Video Downloader"

    class InputsSchema(BaseWidget.InputsSchema):
        url: str = Field("https://www.youtube.com/watch?v=dQw4w9WgXcQ", description="YouTube视频URL")
        output_path: str = Field("output/youtube_downloads", description="下载文件保存路径")
        resolution: str = Field("144p", description="视频分辨率 (720p, 480p, 360p, 240p, 144p)")
        convert_to_mp3: bool = Field(True, description="是否将视频转换为MP3")

    class OutputsSchema(BaseWidget.OutputsSchema):
        success: bool = Field(description="下载是否成功")
        message: str = Field(description="状态消息")
        file_path: str = Field("", description="下载视频文件的路径")
        mp3_path: str = Field("", description="转换后的MP3文件路径")
        video_title: str = Field("", description="视频标题")
        channel_name: str = Field("", description="频道名称")
        video_description: str = Field("", description="视频简介")
        myshell_url: str = Field("", description="MP3文件在MyShell上的URL")
        mp4_url: str = Field("", description="原始MP4下载链接")

    def _normalize_filename(self, title: str) -> str:
        """规范化文件名，替换无效字符"""
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            title = title.replace(char, '_')
        return title
        
    def _convert_to_mp3(self, video_path, output_dir, filename):
        """将MP4转换为MP3"""
        mp3_path = output_dir / f"{filename}.mp3"
        
        try:
            logging.info(f"开始将视频转换为MP3: {video_path}")
            video = VideoFileClip(str(video_path))
            video.audio.write_audiofile(str(mp3_path))
            video.close()
            logging.info(f"MP3转换完成: {mp3_path}")
            return mp3_path
        except Exception as e:
            logging.error(f"MP3转换失败: {repr(e)}")
            raise
            
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
        valid_resolutions = ['720p', '480p', '360p', '240p', '144p']
        if resolution not in valid_resolutions:
            raise ValueError(f"分辨率必须是以下之一: {', '.join(valid_resolutions)}")
        return True

    def execute(self, environ, config):
        """
        执行YouTube视频下载

        Args:
            environ: 环境变量
            config: 配置参数，包含url，output_path等

        Returns:
            包含下载结果的字典
        """
        try:
            # 从环境变量获取Apify API密钥
            apify_api_key = os.environ.get("APIFY_API_KEY")
            
            # 如果环境变量中没有API密钥，返回错误
            if not apify_api_key:
                return {
                    "success": False,
                    "message": "缺少APIFY_API_KEY环境变量，请设置后再试",
                    "file_path": "",
                    "mp3_path": "",
                    "video_title": "",
                    "channel_name": "",
                    "video_description": "",
                    "myshell_url": "",
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
                    "file_path": "",
                    "mp3_path": "",
                    "video_title": "",
                    "channel_name": "",
                    "video_description": "",
                    "myshell_url": "",
                    "mp4_url": ""
                }
            
            # 创建输出目录
            output_dir = Path(config.output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            # 创建Apify客户端
            client = ApifyClient(apify_api_key)
            
            # 准备Actor输入参数
            run_input = {
                "urls": [config.url],
                "resolution": config.resolution,
                "max_concurrent": 1,
            }

            # 运行Actor并等待完成
            run = client.actor("QrdkHOap2H2LvbyZk").call(run_input=run_input)
            
            # 获取结果
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                return {
                    "success": False,
                    "message": "无法获取视频信息",
                    "file_path": "",
                    "mp3_path": "",
                    "video_title": "",
                    "channel_name": "",
                    "video_description": "",
                    "myshell_url": "",
                    "mp4_url": ""
                }
            
            video_info = items[0]
            
            # 提取视频信息
            title = video_info.get("title", "未知标题")
            filename = self._normalize_filename(title)
            
            result = {
                "success": True,
                "message": f"视频成功下载: {title}",
                "file_path": "",
                "mp3_path": "",
                "video_title": title,
                "channel_name": video_info.get("channel", ""),
                "video_description": video_info.get("description", ""),
                "myshell_url": "",
                "mp4_url": ""
            }
            
            # 下载链接
            download_url = video_info.get("download_url", "")
            result["mp4_url"] = download_url
            
            if not download_url:
                return {
                    "success": False,
                    "message": "未找到下载链接",
                    "file_path": "",
                    "mp3_path": "",
                    "video_title": title,
                    "channel_name": video_info.get("channel", ""),
                    "video_description": video_info.get("description", ""),
                    "myshell_url": "",
                    "mp4_url": ""
                }
            
            # 下载视频
            file_path = self._download_video(download_url, output_dir, filename)
            result["file_path"] = str(file_path)
            
            # 如果需要转换为MP3
            if config.convert_to_mp3:
                mp3_path = self._convert_to_mp3(file_path, output_dir, filename)
                result["mp3_path"] = str(mp3_path)
                result["message"] += f"，并已转换为MP3"
                
                # 上传MP3到myshell
                try:
                    myshell_url = upload_file_to_myshell(str(mp3_path))
                    result["myshell_url"] = myshell_url
                    logging.info(f"MP3已上传到myshell: {myshell_url}")
                except Exception as e:
                    logging.error(f"上传MP3到myshell失败: {repr(e)}")
                    result["myshell_url"] = ""
            
            return result

        except Exception as e:
            # 记录错误并处理
            logging.error(f"下载失败: {repr(e)}")
            return {
                "success": False,
                "message": f"下载失败: {repr(e)}",
                "file_path": "",
                "mp3_path": "",
                "video_title": "",
                "channel_name": "",
                "video_description": "",
                "myshell_url": "",
                "mp4_url": ""
            }

    def _download_video(self, download_url, output_dir, filename):
        """下载视频"""
        file_extension = "mp4"
        file_path = output_dir / f"{filename}.{file_extension}"
        
        # 执行下载
        response = requests.get(download_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(file_path, 'wb') as file:
            if total_size == 0:
                file.write(response.content)
            else:
                downloaded = 0
                for data in response.iter_content(chunk_size=4096):
                    downloaded += len(data)
                    file.write(data)
                    # 可以记录下载进度，但不输出到控制台以避免日志过多
                    if downloaded % (total_size // 10) == 0:
                        logging.info(f"下载进度: {downloaded}/{total_size} 字节 ({downloaded/total_size:.1%})")
        
        logging.info(f"视频下载完成: {file_path}")
        return file_path


if __name__ == "__main__":
    # 必须在运行前设置环境变量
    # os.environ["APIFY_API_KEY"] = "你的APIFY_API_KEY"
    
    widget = YouTubeDownloaderWidget()
    test_config = {
        "url": "https://www.youtube.com/watch?v=hz6oys4Eem4",
        "output_path": "test_output",
        "resolution": "144p",
        "convert_to_mp3": True
    }

    result = widget({}, test_config)
    print(result)
