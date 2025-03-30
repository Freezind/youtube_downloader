import os
import re
import logging
from pathlib import Path
from typing import Any, Optional
from pydantic import Field, validator

from proconfig.widgets.base import WIDGETS, BaseWidget
from proconfig.utils.misc import upload_file_to_myshell

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
        download_subtitles: bool = Field(False, description="下载英文字幕")

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
        video_description: Optional[str] = Field(None, description="视频简介")
        channel_description: Optional[str] = Field(None, description="频道简介")
        subtitle_path: Optional[str] = Field(None, description="字幕文件路径")
        myshell_url: Optional[str] = Field(None, description="MyShell上传后的URL")

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

            # 获取视频描述和频道信息
            video_description = yt.description
            # 获取频道描述信息（注意：pytubefix可能无法直接获取频道描述，此处为空）
            channel_description = ""

            result = {
                "success": True,
                "message": f"视频成功下载: {yt.title}",
                "file_path": None,
                "video_title": yt.title,
                "channel_name": yt.author,
                "video_description": video_description,
                "channel_description": channel_description,
                "subtitle_path": None,
                "myshell_url": None
            }

            if config.audio_only:
                # 下载音频
                file_path, myshell_url = self._download_audio(yt, output_dir, filename)
                result["file_path"] = str(file_path)
                result["myshell_url"] = myshell_url

            else:
                # 下载视频
                file_path = self._download_video(yt, output_dir, filename, config.resolution)
                result["file_path"] = str(file_path)

            # 如果需要下载字幕
            if config.download_subtitles:
                subtitle_path = self._download_subtitles(yt, output_dir, filename)
                result["subtitle_path"] = str(subtitle_path) if subtitle_path else None
                if subtitle_path:
                    result["message"] += "，并成功下载英文字幕"
                else:
                    result["message"] += "，但该视频没有可用的英文字幕"

            return result

        except Exception as e:
            # 记录错误并处理

            logging.error(f"下载失败: {repr(e)}")
            return {
                "success": False,
                "message": f"下载失败: {repr(e)}",
                "file_path": None,
                "video_title": None,
                "channel_name": None,
                "video_description": None,
                "channel_description": None,
                "subtitle_path": None,
                "myshell_url": None
            }



    def _download_audio(self, yt, output_dir, filename):
        """下载音频流"""
        stream = yt.streams.get_audio_only()
        file_extension = "mp3"  # 音频格式通常为m4a
        file_path = output_dir / f"{filename}.{file_extension}"
        print(f"DEBUG 下载音频文件: {file_path}")

        # 执行下载
        stream.download(output_path=str(output_dir), filename=f"{filename}.{file_extension}")

        # 上传到myshell
        try:
            myshell_url = upload_file_to_myshell(str(file_path))
            logging.info(f"Audio file uploaded to myshell: {myshell_url}")
        except Exception as e:
            logging.error(f"Failed to upload audio to myshell: {repr(e)}")
            myshell_url = None

        return file_path, myshell_url

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

    def _download_subtitles(self, yt, output_dir, filename):
        auto_captions = {}
        try:
            for k, v in yt.captions.items():
                print(k)
                if k.startswith('a'):
                    auto_captions[k] = v
        except KeyError as e:            # 尝试直接访问特定字幕
            if 'a.en' in yt.captions:
                auto_captions['a.en'] = yt.captions['a.en']
            elif len(yt.captions) > 0:
                # 获取第一个可用字幕
                first_key = list(yt.captions)[0]
                auto_captions[first_key] = yt.captions[first_key]
        if auto_captions:
            # 获取第一个可用的自动字幕
            subtitle_code = list(auto_captions.keys())[0]
            subtitles = yt.captions[subtitle_code]
            subtitle_path = output_dir / f"{filename}{subtitle_code}.srt"
            subtitles.download(output_path=str(output_dir), title=f"{filename}{subtitle_code}.srt")
            return subtitle_path
        else:
            return None


if __name__ == "__main__":

    widget = YouTubeDownloaderWidget()
    test_config = {
        "url": "https://www.youtube.com/watch?v=hz6oys4Eem4",
        "output_path": "test_output",
        "resolution": "highest",
        "filename": None,
        "audio_only": True,
        "download_subtitles": True
    }

    result = widget({}, test_config)
    print(result)
