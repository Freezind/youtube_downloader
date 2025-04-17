# YouTube 下载器 Widget

这是一个用于ShellAgent的自定义Widget，可以获取YouTube视频的下载链接。

## 功能特点

- 支持获取不同分辨率的YouTube视频下载链接
- 使用Apify API获取下载链接
- **缓存功能**：将下载链接缓存到Apify KV存储中，避免重复请求
- **链接有效性检查**：检查缓存链接是否有效，无效则重新获取
- 支持YouTube短视频(Shorts)链接
- 可配置代理选项，支持使用住宅代理和选择代理国家/地区

## 安装

1. 确保你已经安装了ShellAgent
2. 将此Widget放在ShellAgent的`custom_widgets`目录下
3. 安装所需依赖：

```bash
pip install -r custom_widgets/youtube_downloader/requirements.txt
```

## 使用方法

### 环境变量设置

在使用Widget之前，需要设置Apify API密钥：

```bash
export APIFY_API_KEY="你的Apify API密钥"
```

Windows系统可以使用以下命令：

```bash
set APIFY_API_KEY=你的Apify API密钥
```

### 参数配置

Widget接受以下配置参数：

- `url`: YouTube视频URL (必须)
- `resolution`: 视频分辨率，可选值为 "2160", "1440", "1080", "720", "480", "360", "240", "144" (默认: "360")
- `use_residential_proxy`: 是否使用住宅代理 (默认: false)
- `proxy_country`: 代理服务器国家/地区代码 (默认: "US")
- `force_refresh`: 是否强制刷新缓存 (默认: false)

### 返回值

Widget返回一个包含以下字段的字典：

- `success`: 操作是否成功 (boolean)
- `message`: 状态消息 (string)
- `mp4_url`: MP4下载链接 (string)
- `cached`: 是否使用了缓存 (boolean)

## 缓存机制

Widget使用Apify Key-Value存储作为缓存机制：

1. 每当获取新的下载链接时，会自动存储到Apify KV存储中
2. 下次请求相同URL和分辨率的视频时，会先尝试从缓存获取链接
3. 会检查缓存链接的有效性，如果无效会自动重新获取
4. 可以通过设置`force_refresh=true`强制刷新缓存

## 测试

可以使用提供的测试脚本测试Widget功能：

```bash
python custom_widgets/youtube_downloader/test_widget.py
```

## 依赖

- apify-client>=1.4.1
- python-slugify>=8.0.1
- requests>=2.28.0
- easydict>=1.9
- moviepy==1.0.3

## 注意事项

- 请确保遵守YouTube的服务条款
- 该Widget仅提供下载链接，不直接下载视频
- 下载链接有时效性，请及时使用
- Apify API有使用限制，请注意配额
