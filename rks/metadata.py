from __future__ import annotations

import json
from pathlib import Path
import re
import zlib
from .export import binary, run
from .importers import KRC_KEY

FIELDS = ('title', 'original_artist', 'lyricist', 'composer', 'arranger', 'mv_director')
ALIASES = {
    'title': ('title', 'track', 'song'),
    'original_artist': ('original_artist', 'originalartist', 'original performer', 'singer', 'artist', 'performer'),
    'lyricist': ('lyricist', 'lyrics_by', 'words_by', 'text_by', 'text'),
    'composer': ('composer', 'music_by', 'composed_by', 'music', 'tcom'),
    'arranger': ('arranger', 'arranged_by', 'arrangement'),
    'mv_director': ('mv_director', 'music_video_director', 'video_director', 'director'),
}
LYRIC_ALIASES = {
    'title': ('ti', 'title'),
    'original_artist': ('ar', 'artist', 'original_artist', 'singer'),
    'lyricist': ('lyricist', 'lyrics_by', 'words_by'),
    'composer': ('composer', 'music_by'),
    'arranger': ('arranger', 'arranged_by'),
    'mv_director': ('mv_director', 'video_director', 'director'),
}


def audio_tags(path: str) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    result = run([binary('ffprobe'), '-v', 'error', '-show_entries', 'format_tags:stream_tags', '-of', 'json', path])
    parsed = json.loads(result.stdout)
    tags: dict[str, str] = {}
    for source in [parsed.get('format', {}), *parsed.get('streams', [])]:
        for key, value in source.get('tags', {}).items():
            normalized = key.strip().lower().replace(' ', '_').replace('-', '_')
            if value and normalized not in tags:
                tags[normalized] = str(value).strip()
    return tags


def lyric_tags(path: str) -> dict[str, str]:
    if not path or not Path(path).exists():
        return {}
    data = Path(path).read_bytes()
    if Path(path).suffix.lower() == '.krc' and data.startswith(b'krc1'):
        encoded = bytes(byte ^ KRC_KEY[i % len(KRC_KEY)] for i, byte in enumerate(data[4:]))
        data = zlib.decompress(encoded)
    content = None
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030', 'big5'):
        try:
            content = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        return {}
    tags: dict[str, str] = {}
    for raw in content.splitlines():
        match = re.match(r'^\[([A-Za-z_][\w -]*):(.+?)\]\s*$', raw.strip())
        if match:
            key = match.group(1).strip().lower().replace(' ', '_').replace('-', '_')
            tags[key] = match.group(2).strip()
        elif Path(path).suffix.lower() == '.ass':
            match = re.match(r'^Title:\s*(.+)$', raw, re.I)
            if match and 'title' not in tags:
                tags['title'] = match.group(1).strip()
    return tags


def discover_credits(audio: str = '', lyrics: str = '') -> dict[str, tuple[str, str]]:
    """Return only fields that were actually found; never invent missing credits."""
    music = audio_tags(audio)
    lyric = lyric_tags(lyrics)
    found: dict[str, tuple[str, str]] = {}
    for field in FIELDS:
        for alias in ALIASES[field]:
            if music.get(alias):
                source = f'音频标签 {alias}'
                if field == 'original_artist' and alias in ('artist', 'performer'):
                    source += '（请核对是否原唱）'
                found[field] = music[alias], source
                break
        if field not in found:
            for alias in LYRIC_ALIASES[field]:
                if lyric.get(alias):
                    found[field] = lyric[alias], f'歌词标签 {alias}'
                    break
    if 'title' not in found and audio:
        found['title'] = Path(audio).stem, '文件名（请核对）'
    return found
