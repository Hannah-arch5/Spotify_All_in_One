# YouTube 字幕可行性评估

## 结论

可以把 YouTube 字幕作为 transcript 的第一优先来源，并停止默认音频转写。

推荐顺序：

1. 官网 / Substack / 播客页面自带 transcript。
2. 官方 YouTube 视频字幕。
3. Language Reactor 在 YouTube 页面显示的完整字幕，作为验证和辅助提取来源。
4. Spotify 页面 transcript，作为人工或插件辅助来源。
5. 仍无 transcript 时，标记为 `transcript_missing`，不做事实性深度总结。

不建议默认 ASR 转写，因为每 2-3 天一次、每次十几到二十几集，成本和处理时间都会持续累积。

## YouTube 字幕的优点

- 基本没有转写费用。
- 自动字幕通常带时间戳，可用于研报引用。
- 很多英文大播客有官方 YouTube 视频版。
- 对后续“字幕 / 翻译 / 搜索库”项目很有复用价值。

## YouTube 字幕的限制

- YouTube 官方 Data API 的 captions 下载通常需要视频所有者 OAuth 权限，不适合作为通用批量抓取方案。
- 实际工程上通常用 `yt-dlp` 或 `youtube-transcript-api` 一类工具读取公开字幕轨道。
- 并非每个 podcast episode 都会同步到 YouTube。
- 同步时间可能晚于 RSS 发布时间，需要允许 6-24 小时延迟重试。
- 标题匹配可能出错，必须用官方频道、发布时间、标题相似度、时长接近度做校验。

## Language Reactor 插件的使用方式

用户的 Chrome 和 Comet 里都有 Language Reactor。它可以作为一个很好的低成本字幕入口：

- 如果 Language Reactor 能显示完整字幕，通常说明该 YouTube 视频存在可用字幕轨道。
- 自动化时优先尝试直接读取 YouTube 底层字幕轨道，而不是操作插件 UI。
- 如果底层字幕读取失败，再用 Chrome/Comet 打开 YouTube 页面，通过 Language Reactor 的字幕面板复制或导出 transcript。
- Language Reactor 更适合作为 fallback 或人工校验工具，不建议作为唯一主链，因为插件 UI 可能升级、页面结构可能变化。

推荐策略：

1. 用 RSS episode 标题匹配官方 YouTube 视频。
2. 尝试程序化读取 YouTube captions。
3. 如果失败，用 Chrome 打开该视频，检查 Language Reactor 是否显示完整字幕。
4. 如果能显示，则复制/导出字幕，保存为标准 transcript JSON。
5. 如果仍失败，标记为 `transcript_missing`。

## 当前播客清单的覆盖判断

### 高可行性

这些节目大概率有官方 YouTube 视频版或官网 transcript，可以作为主要 transcript 来源：

- All-In with Chamath, Jason, Sacks & Friedberg
- Latent Space: The AI Engineer Podcast
- Dwarkesh Podcast
- BG2Pod with Brad Gerstner and Bill Gurley
- No Priors
- Lenny's Podcast
- Acquired
- The Diary Of A CEO with Steven Bartlett
- Modern Wisdom
- Lex Fridman Podcast
- Lightcone Podcast

### 中等可行性

这些节目可能有 YouTube 或官网内容，但不是每期都稳定：

- The a16z Show
- Google DeepMind: The Podcast
- Invest Like the Best
- Minus One
- Long Strange Trip
- Cheeky Pint
- Behind the Craft
- The AI Daily Brief
- 小Lin说

### 低可行性

这些更可能需要官网、RSS shownotes、Spotify transcript 或直接标记缺失：

- Exchanges
- The Markets
- The Joe Rogan Experience
- 硅谷101
- 厚雪长波
- 张小珺Jùn | 商业访谈录

## 建议实现方案

### 1. 为每个播客补官方 YouTube 频道

在 `config/podcasts.yaml` 增加：

```yaml
youtube_channel_url: null
youtube_match: "high" | "medium" | "low"
transcript_strategy:
  - "official_page"
  - "youtube_captions"
  - "spotify_plugin"
```

### 2. 建立匹配规则

对每个新 episode：

1. 用 episode 标题 + 播客名搜索 YouTube。
2. 只接受官方频道或白名单频道。
3. 标题相似度必须足够高。
4. 发布时间和 RSS 发布时间相差不超过 3 天。
5. 如果 RSS 有时长，YouTube 视频时长差异不超过 20%。
6. 匹配失败则进入 `retry_later`，不要直接判定失败。

### 3. 获取字幕

优先级：

1. 手工字幕 / creator captions。
2. 自动字幕 / auto captions。
3. 自动翻译字幕只作为辅助，不作为事实依据。

保存格式：

```json
{
  "episode_id": "...",
  "source": "youtube_captions",
  "youtube_url": "...",
  "caption_kind": "manual|auto",
  "language": "en",
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "..."}
  ]
}
```

### 4. 对没字幕的节目降级处理

如果没有可用 transcript：

- 不做深度事实总结。
- 只基于 RSS shownotes 输出“待补 transcript”短条目。
- Telegram / 研报里列入“未纳入深度分析原因”。

## 对第一份 26 条研报的建议

先跑 YouTube 字幕匹配。预计：

- 约 40%-60% 有机会直接拿到 YouTube 字幕或官网 transcript。
- AI / 科技 / 大主播英文播客覆盖率更高。
- Goldman Sachs、中文播客、Joe Rogan 这类覆盖率会低一些。

这比默认云端 ASR 更适合长期定时流程。
