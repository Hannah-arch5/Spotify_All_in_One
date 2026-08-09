# Spotify Podcast Transcript Collector

这是从用户已有的 Spotify Transcript Downloader 复制出的项目版，保留原插件不动。

## 工作机制

插件会注入脚本到 `open.spotify.com` 页面，拦截包含以下关键词的网络请求：

- `transcript`
- `episode-transcripts`

当 Spotify 页面加载 transcript 数据后，插件会：

1. 捕获 transcript JSON。
2. 用 episode id 存入 Chrome 本地扩展 storage。
3. 自动下载 JSON 到浏览器默认下载目录：

```text
Spotify Transcript Collector/
```

## 安装

1. 打开 `chrome://extensions`。
2. 开启 `Developer mode`。
3. 点击 `Load unpacked`。
4. 选择：

```text
/Users/hannah/Documents/Spotify All in One/chrome-spotify-transcript-downloader
```

建议先禁用旧版 `Spotify Podcast Transcript Downloader`，避免两个插件同时拦截和下载。

## 使用

1. 打开 `https://open.spotify.com/episode/...`。
2. 如果 Spotify 页面有 transcript，点击页面里的 Transcript，或播放/展开 transcript。
3. 插件捕获后会自动下载 JSON。
4. 如果右下角出现下载按钮，可以再次点击重新下载。

## 优点

- 不需要音频转写。
- 不需要找 YouTube 对应视频。
- episode 对应关系更准确。
- 可作为本项目 transcript 获取的最高优先级来源。

## 限制

- 只有 Spotify 页面实际提供 transcript 时才可用。
- 需要 transcript 网络请求发生一次，插件才能捕获。
- 如果 Spotify 网页结构或接口改版，需要更新拦截规则。
