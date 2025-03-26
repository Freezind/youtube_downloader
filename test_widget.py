"""
YouTubeDownloaderWidget 测试脚本
用于测试 YouTube 下载器 Widget 功能
"""
import os
import logging
from pathlib import Path
from easydict import EasyDict

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

def test_widget():
    """测试YouTube下载器widget的基本功能"""
    # 创建widget实例
    widget = YouTubeDownloaderWidget()
    
    # 创建测试输出目录
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # 测试配置
    test_config = EasyDict({
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # 经典测试视频
        "output_path": str(output_dir),
        "resolution": "highest",
        "filename": None,
        "audio_only": True
    })
    
    # 执行widget
    logger.info("开始测试widget (音频下载)...")
    try:
        result = widget.execute({}, test_config)
        
        if result['success']:
            logger.info("音频下载测试通过!")
            logger.info(f"视频标题: {result['video_title']}")
            logger.info(f"频道: {result['channel_name']}")
            logger.info(f"文件路径: {result['file_path']}")
            
            # 验证文件是否存在
            if os.path.exists(result['file_path']):
                logger.info("文件已成功下载并存在!")
            else:
                logger.error("文件下载声称成功，但文件不存在!")
                return False
            
            # 可选：测试视频下载
            if input("是否测试视频下载? (y/n): ").lower() == 'y':
                test_config.audio_only = False
                logger.info("开始测试widget (视频下载)...")
                
                video_result = widget.execute({}, test_config)
                if video_result['success']:
                    logger.info("视频下载测试通过!")
                    logger.info(f"文件路径: {video_result['file_path']}")
                else:
                    logger.error(f"视频下载测试失败: {video_result['message']}")
            
            return True
        else:
            logger.error(f"测试失败: {result['message']}")
            return False
            
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 检查依赖
    try:
        import pytubefix
        from pydantic import Field
    except ImportError as e:
        logger.error(f"缺少必要依赖: {e}")
        logger.info("请先安装依赖: pip install -r requirements.txt")
    else:
        # 运行测试
        success = test_widget()
        print(f"\n测试结果: {'成功' if success else '失败'}") 