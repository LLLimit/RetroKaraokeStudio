from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable
from .ass import save_ass
from .model import Project


def binary(name: str) -> str:
    local = Path(__file__).resolve().parent.parent / 'bin' / f'{name}.exe'
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f'找不到 {name}；请安装 FFmpeg 或将其放入 bin 目录')
    return found


def run(args: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(result.stderr[-3500:])
    return result


def probe_duration(path: str) -> float:
    result = run([binary('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', path])
    return float(result.stdout.strip())


def video_info(path: str) -> dict:
    result = run([binary('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                  'stream=codec_name,pix_fmt,width,height,r_frame_rate', '-of', 'json', path])
    return json.loads(result.stdout)['streams'][0]


def _filter(project: Project, ass_name: str, transparent: bool, bg: str = 'black') -> str:
    source = 'black@0.0' if transparent else bg.replace('#', '0x')
    soften = ',gblur=sigma=0.35' if project.style.soft else ''
    return (f'color=c={source}:s={project.width}x{project.height}:r={project.fps},'
            f'format=rgba,colorchannelmixer=aa={0 if transparent else 1},'
            f'ass={ass_name}:alpha=1{soften},format=' + ('yuva444p10le' if transparent else 'yuv420p'))


def export_video(project: Project, output: str | Path, mode: str = 'prores', background: str = 'black',
                 progress: Callable[[float], None] | None = None) -> Path:
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = project.duration or (max((line.end for line in project.lines), default=0) + .5)
    with tempfile.TemporaryDirectory(prefix='rks_') as temp:
        save_ass(project, Path(temp) / 'lyrics.ass')
        transparent = mode in ('prores', 'png')
        preview_color = project.style.preview_background if background == 'black' else background
        filt = _filter(project, 'lyrics.ass', transparent, preview_color)
        args = [binary('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-progress', 'pipe:1', '-nostats',
                '-f', 'lavfi', '-i', filt]
        has_audio = bool(project.audio and Path(project.audio).exists() and mode != 'png')
        if has_audio:
            args += ['-i', project.audio]
        args += ['-t', f'{duration:.3f}', '-r', str(project.fps), '-map', '0:v:0']
        if has_audio:
            args += ['-map', '1:a:0']
        if mode == 'prores':
            args += ['-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16', '-vendor', 'apl0',
                     '-c:a', 'pcm_s16le' if has_audio else 'copy', str(output)]
        elif mode == 'png':
            output.mkdir(parents=True, exist_ok=True)
            args += ['-c:v', 'png', '-pix_fmt', 'rgba', str(output / 'frame_%06d.png')]
        elif mode == 'mp4':
            args += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
                     '-c:a', 'aac' if has_audio else 'copy', '-b:a', '192k', str(output)]
        else:
            raise ValueError(mode)
        if progress is None:
            run(args, cwd=temp)
        else:
            process = subprocess.Popen(args, cwd=temp, text=True, encoding='utf-8', errors='replace',
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            assert process.stdout is not None
            try:
                for entry in process.stdout:
                    if entry.startswith('out_time='):
                        clock = entry.partition('=')[2].strip()
                        try:
                            hours, minutes, seconds = clock.split(':')
                            elapsed = int(hours)*3600 + int(minutes)*60 + float(seconds)
                            progress(min(.999, max(0.0, elapsed / max(.001, duration))))
                        except ValueError:
                            pass
                error = process.stderr.read() if process.stderr else ''
            finally:
                process.stdout.close()
                if process.stderr: process.stderr.close()
            if process.wait():
                raise RuntimeError(error[-3500:] or 'FFmpeg 导出失败')
            progress(1.0)
    return output


def alpha_samples(video: str | Path, seconds: list[float] | None = None) -> list[dict]:
    samples = []
    for second in seconds or [0.0, 1.0]:
        info = video_info(str(video))
        width, height = int(info['width']), int(info['height'])
        raw = subprocess.run([binary('ffmpeg'), '-v', 'error', '-ss', str(second), '-i', str(video),
                              '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                             capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if raw.returncode or len(raw.stdout) < width * height * 4:
            raise RuntimeError(raw.stderr.decode(errors='replace'))
        alpha = raw.stdout[3::4]
        samples.append({'second': second, 'corner_alpha': alpha[0],
                        'transparent_pixels': sum(x == 0 for x in alpha),
                        'visible_pixels': sum(x > 0 for x in alpha),
                        'pixel_count': width * height})
    return samples
