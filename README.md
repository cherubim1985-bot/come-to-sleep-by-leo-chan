# 每日冥想视频自动化项目

这个目录现在包含两套能力：

1. `meditation_video_builder.py`
   单次生成一个冥想视频素材包。
2. `daily_meditation_pipeline.py`
   面向“每天自动生成一条冥想视频”的项目主入口。

## 每日自动化会生成什么

每天运行一次后，会在 `output/` 下生成一个日期目录，里面包含：

- 当天冥想主题
- 中文冥想指引词
- `cover.svg` 静态封面
- `image_prompt.txt` 图片生成提示词
- `music_prompt.txt` 音乐生成提示词
- `music_request.json` 音乐生成请求
- `music_generation_result.json` 音乐生成结果
- `captions.srt` 字幕
- `voiceover_request.json` 克隆音色请求载荷
- `bundle_manifest.json` 剪映导入清单
- 选中的背景音乐副本
- `剪映导入说明.md`

## 快速开始

先初始化项目文件：

```bash
python3 daily_meditation_pipeline.py --bootstrap-only
```

然后生成今天的冥想视频素材包：

```bash
python3 daily_meditation_pipeline.py
```

如果要生成指定日期：

```bash
python3 daily_meditation_pipeline.py --date 2026-03-15
```

## 需要你补充的内容

### 1. 克隆声音配置

编辑 [config/project_config.json](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/config/project_config.json)：

- `voice_clone.provider`
- `voice_clone.voice_id`
- `voice_clone.speaker_name`
- `voice_clone.instructions`

当前默认已经切到 `volcengine_v1`。如果克隆声音链路不可用，脚本现在会直接失败，不再回退到其他声音。

如果你要直接使用火山引擎：

- 把 `voice_clone.provider` 改成 `volcengine_v1`
- 填入 `voice_clone.volcengine.api_key`
- 填入 `voice_clone.volcengine.speaker`
- 如有需要，调整 `cluster / speed_ratio / audio_format`

说明：这条路线按长文本异步方式提交任务，更适合 `15-30` 分钟冥想旁白。

如果你要自动生成克隆旁白：

- 把 `voice_clone.provider` 改成 `elevenlabs`
- 填入 `voice_clone.api_key`
- 填入 `voice_clone.voice_id`
- 可选调整 `voice_clone.model_id` 和 `voice_clone.output_format`

如果你要试更像真人的本地免费方案：

- 把 `voice_clone.provider` 改成 `cosyvoice_local`
- 填入 `voice_clone.reference_audio`
- 可选填 `voice_clone.reference_transcript`
- 准备 CosyVoice2 模型到 `third_party/CosyVoice/pretrained_models/CosyVoice2-0.5B`
- 使用 [tools/cosyvoice_runner.py](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/tools/cosyvoice_runner.py)

如果你要试更像、但更重一些的本地方案：

- 把 `voice_clone.provider` 改成 `indextts_local`
- 填入 `voice_clone.reference_audio`
- 确保 [third_party/index-tts](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/third_party/index-tts) 已完成依赖和权重安装
- 使用 [tools/indextts_runner.py](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/tools/indextts_runner.py)

说明：`IndexTTS` 在音色方向上通常更接近真人，但本机 CPU 推理明显更慢，适合做高相似度测试，不适合直接在这台机器上长时间批量生成。

### 2. 时长设置

每日视频时长现在支持自动随机。

- `duration_mode = "random_range"`：每天在区间内自动取一个随机时长
- `duration_min_minutes`：最小时长
- `duration_max_minutes`：最大时长
- `default_duration_minutes`：固定模式或兜底时长

当前默认配置是每天自动生成一个 `15-30` 分钟之间的时长，同一天重复生成会保持一致，方便重跑。

另外，`script_style` 默认已经是 `human_spoken`，会尽量生成更像真人老师口播的冥想引导，而不是机械段落模板。

### 3. 冥想音乐库

把背景音乐放进 [assets/music](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/assets/music)。

如果这个目录为空，脚本会回退到根目录里的 `0208 (1).MP3`。

如果你想让音乐和主题自动匹配：

- 把多首音乐放进 `assets/music`
- 在 [assets/music/music_library.json](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/assets/music/music_library.json) 里给每首音乐打标签
- 脚本会优先选和主题标签更接近、且最近较少重复的音乐

如果你想直接自动生成新音乐：

- 编辑 [config/project_config.json](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/config/project_config.json) 里的 `music_generation`
- 把 `provider` 改成 `webhook`
- 填入你的音乐生成接口 `endpoint` 和鉴权 `auth_header`
- 脚本会尝试自动调用接口，并把返回的音频保存到当天输出目录

### 3. 静态图片 API

如果你要自动生成每日冥想静态图：

- 把 `image_generation.provider` 改成 `openai`
- 填入 `image_generation.api_key`
- 可选调整 `model`、`size`、`quality`

脚本会自动生成：

- `image_request.json`
- `image_generation_result.json`
- 实际图片文件，例如 `2026-03-20-睡前释放-image.png`

### 4. 主题库

编辑 [config/theme_library.json](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/config/theme_library.json) 可以增加更多主题。

当前文案生成器已经不再只用固定模板，而会自动融合多种冥想传统，例如：

- 观息与内观
- 身体扫描
- 慈心观
- 禅宗观照
- 瑜伽尼德拉
- 道家松静
- 行禅式觉察
- 视觉观想
- 盒式呼吸
- 4-7-8 呼吸
- 数息法
- 声音锚定
- 咒音专注

脚本会根据主题、日期和时长自动混合这些技巧，所以每天生成的引导会更有变化。当天实际使用到的传统会写进 `script.json` 和 `bundle_manifest.json`。

如果你在 [config/theme_library.json](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/config/theme_library.json) 里给主题增加 `practice_preferences`，脚本会更偏向这些技巧。

## 剪映专业版工作流

当前项目已经把“每日素材包”整理好了，但还没有直接操控剪映专业版 UI。现阶段流程是：

1. 每天自动生成一包素材
2. 把克隆音色生成出来
3. 在剪映专业版里一键导入这些素材
4. 套用你的固定模板导出

如果你下一步要，我可以继续把项目往下做成：

1. “接入你指定的克隆声音 API，自动生成旁白音频”
2. “接入图片生成 API，自动生成静态图片”
3. “补一个 macOS 自动打开剪映并导入素材的脚本”
4. “按你的频道风格做固定片头、字幕样式、结尾 CTA”

## 每日自动运行

已经附带一个 macOS `launchd` 模板：

- [generate_today.sh](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/generate_today.sh)
- [launchd/com.xuguangchen.daily-meditation.plist](/Users/xuguangchen/Library/CloudStorage/OneDrive-TulaneUniversity/Video Jianying/launchd/com.xuguangchen.daily-meditation.plist)

默认每天早上 8:00 运行一次。你可以按需调整。

## 网站发布

网站发布目录现在只保留 Cloudflare Pages 版本：

- 发布输出目录：`deploy/cloudflare-pages`
- 站点域名：`https://come-to-sleep-by-leo-chan.pages.dev/`
- `daily_meditation_pipeline.py` 每次生成后都会直接刷新这个目录
- `publish_sleep_site.sh` 提交并推送后，由 Cloudflare Pages 从 GitHub 自动重新部署

仓库里不再保留 `netlify` 命名的发布目录或配置，避免平台混淆。
