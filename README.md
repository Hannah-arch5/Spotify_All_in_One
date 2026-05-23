# Spotify All in One

自动检查关注播客的 RSS 更新，生成可核对的新增 episode 清单。研报正文排序规则固定为：

> 按 episode 发布时间倒序排列，最新发布时间放第一个。

## 当前阶段

已完成第一步主链：

- 维护关注播客配置：`config/podcasts.yaml`
- 读取公开 RSS feed
- 按最近更新时间筛选新增 episode
- 用本地 SQLite 记录已处理 episode，避免重复
- 输出 JSON manifest 和 Markdown 清单

## 目录结构

- `config/`：播客关注清单和流程配置
- `scripts/`：可直接运行的自动化脚本
- `src/`：RSS、配置、去重等底层代码
- `chrome-spotify-transcript-downloader/`：Chrome unpacked extension，暂时不要移动
- `docs/gemini/`：给 Gemini 的生成协议、复查清单和最终 prompt
- `docs/research/`：字幕来源、YouTube/Language Reactor 可行性记录
- `docs/workflow/`：整体流程方案
- `docs/plugin/`：Antigravity 修改插件时要看的注意事项
- `data/`：运行数据和缓存，默认不入 git
- `reports/`：生成的 Markdown/PDF 报告，默认不入 git

## 运行

检查最近 3 天的更新：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_new_episodes.py
```

生成好读的 Markdown 清单：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/render_episode_list.py
```

检查本次 episode 的 transcript 可用性：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/audit_transcripts.py
```

根据 Spotify Transcript Downloader 的下载结果生成 Gemini 证据包：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/import_spotify_transcripts.py
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/build_evidence_pack.py data/runs/20260523-222300-manifest.json
```

如果已经确认字幕归档成功，可以把 Downloads 里的临时副本一起清掉：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/import_spotify_transcripts.py --move
```

清理项目内超过 90 天的旧 transcript，默认先预览不删除：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/prune_transcripts.py
```

确认预览无误后真正删除：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/prune_transcripts.py --delete
```

生成剩余 Spotify transcript 采集队列：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/build_spotify_collection_queue.py data/runs/20260523-222300-evidence-pack.json
```

生成 ASR 转写队列：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/build_transcription_queue.py
```

如果一次研报已经确认完成，再把本次发现的 episode 标记为已处理：

```bash
/Users/hannah/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/check_new_episodes.py --mark-seen
```

## 输出位置

- JSON 运行清单：`data/runs/*-manifest.json`
- Markdown 更新清单：`reports/markdown/*-episode-list.md`
- Transcript 检查报告：`reports/markdown/*-transcript-audit.md`
- Gemini 证据包：`data/runs/*-evidence-pack.json`
- Spotify 字幕采集队列：`data/runs/*-spotify-collection-queue.json`
- Spotify 字幕归档：`data/transcripts/spotify/`
- ASR 转写队列：`data/runs/*-transcription-queue.json`
- RSS 原始缓存：`data/feeds/`
- 去重数据库：`data/state.sqlite`

## 下一步

1. 从 evidence pack 生成 Gemini 输入包。
2. 让 Gemini 基于 transcript 生成研报。
3. 复查 Gemini 研报是否覆盖全部 episode 且无虚构引用。
4. 渲染横向 PDF 研报。
5. 接入 Telegram、Google Drive、Zotero。
