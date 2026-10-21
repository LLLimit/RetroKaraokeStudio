# 依赖与许可核查（2026-10-21）

| 组件 | 本机版本 | 许可 / 核查 | 用途 |
|---|---:|---|---|
| Python | 3.14.6 | [PSF License](https://www.python.org/psf/license/) | 运行时 |
| PySide6 Essentials | 6.12.0 | [LGPLv3/GPLv3 或商业许可](https://doc.qt.io/qtforpython-6/)；本项目使用免费社区版，动态 DLL 随 onedir 包保留 | 桌面界面和音频播放 |
| FFmpeg/FFprobe | 9.0.1 Gyan full build | 本机 `--enable-gpl --enable-version3 --enable-libass`，因此按 [GPLv3](https://ffmpeg.org/legal.html) 处理；[构建来源](https://www.gyan.dev/ffmpeg/builds/) 说明其静态构建为 GPLv3；[FFmpeg 9.0.1 源码](https://ffmpeg.org/download.html) | 离线渲染/探测 |
| libass | 随 FFmpeg 静态构建 | [ISC](https://github.com/libass/libass/blob/master/COPYING) | ASS 渲染 |
| PyInstaller | 6.22.3 | [GPLv2+ 附引导程序例外](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) | EXE 打包，仅构建依赖 |
| OpenCC | 1.4.2 | [Apache License 2.0](https://github.com/BYVoid/OpenCC) | 离线简体转香港繁体 |

FFmpeg 可执行文件与本工具通过子进程交互。若再分发 EXE 文件夹，应保留本许可说明、相应源码获取链接和原始版权通知。Qt DLL 可以从 onedir 包中替换；请勿把它们合并成不可替换的单体文件。请按最终分发用途复核许可证与字体授权。
