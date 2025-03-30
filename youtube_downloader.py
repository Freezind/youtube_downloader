import os
import re
import logging
import wave
import audioop
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from pydantic import Field, validator

from proconfig.widgets.base import WIDGETS, BaseWidget
from proconfig.utils.misc import upload_file_to_myshell

from pytubefix import YouTube

# 导入pydub处理音频
try:
    from pydub import AudioSegment
    import warnings
    # 忽略pydub的ffmpeg警告
    warnings.filterwarnings("ignore", category=RuntimeWarning, 
                           message="Couldn't find ffmpeg or avconv")
    warnings.filterwarnings("ignore", category=RuntimeWarning, 
                          message="Couldn't find ffprobe or avprobe")
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub未安装，将无法进行音频压缩。请通过pip install pydub安装")


# 音频压缩大小阈值(字节)
AUDIO_COMPRESSION_THRESHOLD = 50 * 1024 * 1024  # 50MB

# 检查ffmpeg是否可用
FFMPEG_AVAILABLE = False
try:
    from pydub.utils import which
    FFMPEG_AVAILABLE = which("ffmpeg") is not None or which("avconv") is not None
except:
    pass

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

            result = {
                "success": True,
                "message": f"视频成功下载: {yt.title}",
                "file_path": None,
                "video_title": yt.title,
                "channel_name": yt.author,
                "subtitle_path": None,
                "myshell_url": None
            }

            if config.audio_only:
                # 下载音频
                file_path, myshell_url, compression_message = self._download_audio(yt, output_dir, filename, config)
                result["file_path"] = str(file_path)
                result["myshell_url"] = myshell_url
                result["message"] = f"音频成功下载: {yt.title} {compression_message}"

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
                "subtitle_path": None,
                "myshell_url": None
            }

    def _download_audio(self, yt, output_dir, filename, config):
        """下载音频流"""
        stream = yt.streams.get_audio_only()
        file_extension = "mp3"  # 音频格式通常为m4a
        file_path = output_dir / f"{filename}.{file_extension}"
        print(f"DEBUG 下载音频文件: {file_path}")

        # 执行下载
        stream.download(output_path=str(output_dir), filename=f"{filename}.{file_extension}")
        
        # 检查文件大小，如果超过阈值则压缩
        compression_message = ""
        if os.path.getsize(file_path) > AUDIO_COMPRESSION_THRESHOLD:
            # 尝试使用pydub压缩
            compressed = False
            if PYDUB_AVAILABLE and FFMPEG_AVAILABLE:
                compressed = self._compress_audio_with_pydub(file_path)
            
            # 如果pydub失败或不可用，尝试使用简单方法（如有）
            if not compressed:
                try:
                    # 这里我们只打印一条消息，因为目前没有可靠的纯Python音频压缩方法
                    logging.warning("音频文件大于50MB，但无法压缩。推荐安装ffmpeg以启用压缩功能。")
                    compression_message = "（文件大于50MB，但无法压缩，请安装ffmpeg启用压缩功能）"
                except Exception as e:
                    logging.error(f"备选压缩失败: {repr(e)}")
            else:
                compression_message = "（文件大于50MB，已自动压缩）"
                logging.info(f"音频文件已压缩: {file_path}")

        # 上传到myshell
        try:
            myshell_url = upload_file_to_myshell(str(file_path))
            logging.info(f"Audio file uploaded to myshell: {myshell_url}")
        except Exception as e:
            logging.error(f"Failed to upload audio to myshell: {repr(e)}")
            myshell_url = None

        return file_path, myshell_url, compression_message

    def _compress_audio_with_pydub(self, file_path):
        """使用pydub压缩音频文件，确保小于50MB
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            bool: 压缩是否成功
        """
        if not PYDUB_AVAILABLE:
            logging.error("无法压缩音频：pydub未安装。请通过pip install pydub安装")
            return False
            
        if not FFMPEG_AVAILABLE:
            logging.error("无法压缩音频：ffmpeg未安装。请安装ffmpeg并确保它在系统PATH中")
            logging.error("Windows安装方法: 下载ffmpeg (https://ffmpeg.org/download.html) 或使用 choco install ffmpeg")
            return False
            
        try:
            # 获取原始文件大小
            original_size = os.path.getsize(file_path)
            target_size = AUDIO_COMPRESSION_THRESHOLD
            
            # 加载音频文件
            try:
                audio = AudioSegment.from_file(str(file_path))
            except Exception as e:
                logging.error(f"加载音频文件失败: {repr(e)}")
                return False
            
            # 压缩策略：从较高质量开始，逐步降低
            qualities = [5, 7, 9]  # mp3压缩质量，范围1-9，越大压缩率越高但质量越低
            
            for quality in qualities:
                temp_path = str(file_path) + f".temp_q{quality}.mp3"
                
                try:
                    # 导出时设置压缩质量
                    audio.export(
                        temp_path, 
                        format="mp3", 
                        parameters=["-q:a", str(quality)]
                    )
                    
                    # 检查压缩后的大小
                    compressed_size = os.path.getsize(temp_path)
                    
                    if compressed_size < target_size:
                        # 压缩成功
                        os.replace(temp_path, file_path)
                        logging.info(f"音频文件已压缩: {original_size/1024/1024:.2f}MB -> {compressed_size/1024/1024:.2f}MB")
                        return True
                    else:
                        # 压缩后仍然太大，尝试更高压缩率
                        os.remove(temp_path)
                
                except Exception as e:
                    logging.error(f"压缩尝试(质量{quality})失败: {repr(e)}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            
            # 如果所有尝试都失败，尝试更激进的方法：降低比特率
            try:
                temp_path = str(file_path) + ".temp_final.mp3"
                audio.export(
                    temp_path, 
                    format="mp3", 
                    bitrate="64k"  # 直接设置低比特率
                )
                
                compressed_size = os.path.getsize(temp_path)
                if compressed_size < target_size:
                    os.replace(temp_path, file_path)
                    logging.info(f"音频文件已压缩(低比特率): {original_size/1024/1024:.2f}MB -> {compressed_size/1024/1024:.2f}MB")
                    return True
                else:
                    os.remove(temp_path)
            except Exception as e:
                logging.error(f"最终压缩尝试失败: {repr(e)}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            logging.error("无法将音频压缩到小于50MB")
            return False
                
        except Exception as e:
            logging.error(f"音频压缩出错: {repr(e)}")
            return False

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
        "url": "https://www.youtube.com/watch?v=oFtjKbXKqbg&t=2883s",
        "output_path": "test_output",
        "resolution": "highest",
        "filename": None,
        "audio_only": True,
        "download_subtitles": True
    }

    result = widget({}, test_config)
    print(result)
