# 测试报告 · 2026-10-21

## 环境

Windows 11、Python 3.14.6、PySide6 6.12.0、PyInstaller 6.22.3、FFmpeg/FFprobe 9.0.1 (Gyan full build，含 libass/ProRes)。

## 自动化结果

`python -m unittest discover -s tests -v`：8 项通过，覆盖普通 LRC 估时与句界限、增强 LRC 精确时间、KRC 文本和 krc1 编码解析、ASS Karaoke Tag 往返和双行、项目保存恢复、ProRes/MP4/PNG 输出与 Alpha 像素、编辑器预览与撤销。

`samples/demo_alpha.mov`：1440×1080、25fps、7 秒；FFprobe 读取 `codec_name=prores`、`pix_fmt=yuva444p12le`、音频 `pcm_s16le`。FFmpeg 解码 RGBA 后，0 秒全帧透明；1.2 秒画角 Alpha=0、可见歌词像素 14,481；4.0 秒画角 Alpha=0、可见歌词像素 11,256。可见字形与透明背景均已实测。libass 日志显示使用 DirectWrite，并将 Microsoft JhengHei 解析为 MicrosoftJhengHeiBold；简繁中文字形已在输出截图和预览中目视检查。

逐字填充验证：对样片解码帧统计不透明暖黄色像素，0.8、1.2、1.6 秒依次为 477、1,219、2,029，符合 `\kf` 从左向右逐字填充的预期。

GUI：原生 Windows 渲染截图为 `samples/gui_windows.png`，中文文字、双行波形块、预览样式正常。PyInstaller onedir 包含 `ffmpeg.exe`、`ffprobe.exe`、Qt FFmpeg multimedia plugin。初次打包时 PyInstaller 额外收集的 `icuuc.dll` 与 Windows Qt 依赖冲突，导致 QtWidgets 无法加载；构建脚本已移除该冲突 DLL。最终 EXE 自检退出码 0，成功调用包内 FFmpeg，产生 `yuva444p12le` ProRes，空白处 Alpha=0，歌词帧有 2,802 个可见像素；原始自检结果保存在 `packaged_self_check.json`。

音频播放：加载自动生成的 7 秒 WAV，静音播放 800 ms 后播放器位置推进到 650 ms，错误字符串为空。

长歌曲性能：最终开启轻微柔化的版本，合成 3 分钟、1440×1080、25fps、4500 帧、45 句简繁字幕，ProRes 4444 导出 **38.48 秒**、文件 **148,423,231 字节**。这是无音频合成样本、当前机器上的一次测量，不代表所有硬件和字体组合。

## Premiere 手动检查

本机没有自动执行 Premiere Pro 2025 导入，因此不能声称 PR 兼容性已通过。请打开 `samples/demo_alpha.mov`，将它置于彩色视频轨之上并从零点对齐，检查：透明区透出底层画面；黄色逐字填充连续；中文没有缺字或裁切；PCM 音频与画面同步；1080 高度及 25fps 未被错误解释。再用一次 1920×1080/30fps 导出核对自定义预设。若 PR 对 Alpha 解释不正确，请测试 PNG 序列备选。

## 当前范围

没有自动语音识别、歌词与人声强制对齐；普通 LRC/TXT 仅可估时并手工修正。参考视频在预览中抽帧显示，不与音乐连续同步播放；它不进入透明导出。尚未在另一台未安装开发环境的电脑上验证系统字体和 EXE 运行。VHS 风格使用配色、阴影与轻微静态柔化，未实现动态录像噪声与扫描线；透明歌词层保持干净，便于 PR 后续画面调色。

## 新增片头与双列模式

新增后运行 `python -m unittest discover -s tests -v`：11 项通过。新测试覆盖本地歌词标签解析、缺失字段、手动片头信息保存、左上当前/右下当前歌词交替、单行模式与 ASS 事件输出。GUI 测试使用独立临时恢复文件，不会写入用户的自动恢复项目。

`samples/stagger_demo_alpha.mov` 为新生成的 7 秒原创合成音乐样片，展示蓝字白描边的片头和左上当前/右下下一句的逐字填充。FFprobe：1440×1080、25fps、ProRes、`yuva444p12le`。解码 RGBA 采样：0 秒 1,555,200 像素全透明；0.8 秒片头 60,149 个可见像素；2.8 秒双列歌词 31,390 个可见像素；4.8 秒双列歌词 16,726 个可见像素；各帧左上角 Alpha=0。`samples/intro_frame.png` 与 `samples/stagger_frame.png` 已目视检查，中文字形和相对布局正常。

片头来源只限本地标签与文件名，无法验证实际音乐的“原唱”是否等于标签里的歌手，也无法从声音自动识别作词、作曲、编曲、MV 导演。Premiere Pro 2025 的真实导入仍需用户手动检查，未虚构通过。

新版 PyInstaller 打包成功；`dist/RetroKaraokeStudio/RetroKaraokeStudio.exe --self-check packaged_self_check_v2.json` 在包内调用 FFmpeg/FFprobe 并以退出码 0 完成。输出为 ProRes `yuva444p12le`，0 秒全透明，0.5 秒有 2,802 个非透明像素。具体结果保存在项目根目录 `packaged_self_check_v2.json`。

## 时间轴移动与繁体转换

时间轴现在可在缩放后通过水平滚动条或鼠标滚轮移动可见范围，波形、字块、刻度、播放头和点击定位共用同一时间偏移。OpenCC 1.4.2 `s2hk` 在本地转换歌词文字；字数不变时保留各字原始起止时间和动画类型，字数变化时按原时间跨度重新分配。新增 GUI 测试核对 300 秒歌曲中段平移、时间与像素往返、简转繁和撤销。完整自动化测试为 12 项通过。

重新打包后的 `packaged_self_check_v3.json` 显示退出码 0、ProRes `yuva444p12le`、0 秒全透明，并从包内 OpenCC 成功把“我的头发”转换为“我的頭髮”；说明离线字典已随 EXE 文件夹打包。

## 导出进度与按钮文案

按钮改为“导出透明 MOV”“导出 PNG 序列”“导出预览 MP4”。进度条从 FFmpeg 的 `out_time` 读取实际处理时间；MOV 渲染占 0–95%，随后验证 Alpha，成功后显示 100%。失败时显示错误状态并恢复按钮。新增进度回调测试及 GUI 文案检查；自动化共 13 项通过。界面截图 `samples/gui_export_progress.png` 已目视检查。
