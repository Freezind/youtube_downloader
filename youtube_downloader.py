import os
import re
import logging
from pathlib import Path
from typing import Any, Optional
from pydantic import Field, validator

from proconfig.widgets.base import WIDGETS, BaseWidget


from pytubefix import YouTube



@WIDGETS.register_module()
class YouTubeDownloaderWidget(BaseWidget):
    """
    YouTube视频下载器Widget，支持下载视频和音频。
    """
    CATEGORY = "Custom Widgets/Media Tools"
    NAME = "YouTube Video Downloader"
    
    class InputsSchema(BaseWidget.InputsSchema):
        url: str = Field("", description="YouTube视频URL")
        output_path: str = Field("output/youtube_downloads", description="下载文件保存路径")
        resolution: str = Field("highest", description="视频分辨率 (highest, 720p, 480p, 360p, 240p, 144p)")
        filename: Optional[str] = Field(None, description="保存的文件名 (可选，默认使用视频标题)")
        audio_only: bool = Field(False, description="仅下载音频")
        
        @validator('url')
        def validate_url(cls, url):
            if not url:
                raise ValueError("请提供YouTube视频URL")
            
            # 简单验证YouTube URL格式
            youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
            match = re.match(youtube_regex, url)
            if not match:
                raise ValueError("无效的YouTube URL")
            return url
    
    class OutputsSchema(BaseWidget.OutputsSchema):
        success: bool = Field(description="下载是否成功")
        message: str = Field(description="状态消息")
        file_path: Optional[str] = Field(description="下载文件的路径")
        video_title: Optional[str] = Field(description="视频标题")
        channel_name: Optional[str] = Field(description="频道名称")
    
    def _normalize_filename(self, title: str) -> str:
        """规范化文件名，替换无效字符"""
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            title = title.replace(char, '_')
        return title
        
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
            # 创建输出目录
            output_dir = Path(config.output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建YouTube对象
            yt = YouTube(config.url)
            
            # 设置文件名
            filename = config.filename or yt.title
            # 规范化文件名
            filename = self._normalize_filename(filename)
            
            if config.audio_only:
                # 下载音频
                file_path = self._download_audio(yt, output_dir, filename)
            else:
                # 下载视频
                file_path = self._download_video(yt, output_dir, filename, config.resolution)
            
            return {
                "success": True,
                "message": f"视频成功下载: {yt.title}",
                "file_path": str(file_path),
                "video_title": yt.title,
                "channel_name": yt.author
            }
            
        except Exception as e:
            # 记录错误并处理
            logging.error(f"下载失败: {str(e)}")
            return {
                "success": False,
                "message": f"下载失败: {str(e)}",
                "file_path": None,
                "video_title": None,
                "channel_name": None
            }
    
    def _download_audio(self, yt, output_dir, filename):
        """下载音频流"""
        stream = yt.streams.get_audio_only()
        file_extension = "m4a"  # 音频格式通常为m4a
        file_path = output_dir / f"{filename}.{file_extension}"
        
        # 执行下载
        stream.download(output_path=str(output_dir), filename=f"{filename}.{file_extension}")
        return file_path
    
    def _download_video(self, yt, output_dir, filename, resolution):
        """下载视频流"""
        if resolution == "highest":
            stream = yt.streams.get_highest_resolution()
        else:
            # 尝试获取指定分辨率
            stream = yt.streams.filter(progressive=True, res=resolution).first()
            
            # 如果未找到指定分辨率，回退到最高分辨率
            if not stream:
                stream = yt.streams.get_highest_resolution()
        
        # 获取文件扩展名
        file_extension = stream.mime_type.split('/')[-1]
        file_path = output_dir / f"{filename}.{file_extension}"
        
        # 执行下载
        stream.download(output_path=str(output_dir), filename=f"{filename}.{file_extension}")
        return file_path


if __name__ == "__main__":
    # 简单功能测试
    try:
        widget = YouTubeDownloaderWidget()
        test_config = {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "output_path": "test_output",
            "resolution": "highest",
            "filename": None,
            "audio_only": True
        }
        # 注意：config应该是一个easydict对象而不是普通字典
        from easydict import EasyDict
        result = widget.execute({}, EasyDict(test_config))
        print(result)
    except Exception as e:
        print(f"测试失败: {str(e)}") 