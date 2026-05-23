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
- ASR 转写队列：`data/runs/*-transcription-queue.json`
- RSS 原始缓存：`data/feeds/`
- 去重数据库：`data/state.sqlite`

## 下一步

1. 为每个 episode 获取 transcript。
2. 用 transcript 生成逐集摘要。
3. 渲染横向 PDF 研报。
4. 接入 Telegram、Google Drive、Zotero。
