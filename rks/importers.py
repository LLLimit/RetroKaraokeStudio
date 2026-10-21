from __future__ import annotations

from pathlib import Path
import re
import zlib
from .model import Line, Word

STAMP = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\]')
INLINE = re.compile(r'<(\d+):(\d+(?:\.\d+)?)>')
KRC_STAMP = re.compile(r'^\[(\d+),(\d+)\](.*)$')
KRC_WORD = re.compile(r'<(\d+),(\d+),(\d+)>([^<]*)')
ASS_EVENT = re.compile(r'^Dialogue:\s*(.*)$', re.I)
ASS_TAG = re.compile(r'\{\\(kf|ko|k)(\d+)\}', re.I)


def timestamp(minute: str, second: str) -> float:
    return int(minute) * 60 + float(second)


def parse_lrc(content: str) -> list[Line]:
    entries: list[Line] = []
    for raw in content.splitlines():
        stamps = list(STAMP.finditer(raw))
        if not stamps:
            continue
        body = raw[stamps[-1].end():].strip()
        if not body:
            continue
        markers = list(INLINE.finditer(body))
        clean = INLINE.sub('', body)
        for stamp in stamps:
            start = timestamp(*stamp.groups())
            words: list[Word] = []
            if markers:
                for i, marker in enumerate(markers):
                    text_start = marker.end()
                    text_end = markers[i + 1].start() if i + 1 < len(markers) else len(body)
                    token = body[text_start:text_end]
                    if token:
                        at = timestamp(*marker.groups())
                        words.append(Word(token, at, at, False))
                for i, word in enumerate(words[:-1]):
                    word.end = words[i + 1].start
            entries.append(Line(clean, start, start, words))
    entries.sort(key=lambda x: x.start)
    for i, line in enumerate(entries):
        next_start = entries[i + 1].start if i + 1 < len(entries) else line.start + 4
        line.end = max(line.start + .1, next_start)
        if line.words:
            line.end = max(line.end, line.words[-1].start + .2)
            line.words[-1].end = line.end
        else:
            line.estimate_words()
        line.lane = i % 2
    return entries


def ass_time(value: str) -> float:
    h, m, s = value.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass(content: str) -> list[Line]:
    lines: list[Line] = []
    in_events = False
    for raw in content.splitlines():
        if raw.strip().lower() == '[events]':
            in_events = True
            continue
        if raw.startswith('[') and in_events:
            in_events = False
        match = ASS_EVENT.match(raw) if in_events else None
        if not match:
            continue
        parts = match.group(1).split(',', 9)
        if len(parts) < 10:
            continue
        start, end, body = ass_time(parts[1]), ass_time(parts[2]), parts[9]
        body = body.replace('\\N', '\n')
        words: list[Word] = []
        cursor = start
        for m in re.finditer(r'\{[^}]*\\(kf|ko|k)(\d+)[^}]*\}([^{}]*)', body, re.I):
            token = m.group(3)
            duration = int(m.group(2)) / 100
            if token:
                words.append(Word(token, cursor, cursor + duration, False, m.group(1).lower()))
            cursor += duration
        clean = re.sub(r'\{[^}]*\}', '', body)
        line = Line(clean, start, end, words, len(lines) % 2)
        if not words:
            line.estimate_words()
        lines.append(line)
    return lines


KRC_KEY = bytes((0x40,0x47,0x61,0x77,0x5e,0x32,0x74,0x47,0x51,0x36,0x31,0x2d,0xce,0xd2,0x6e,0x69))


def parse_krc(data: bytes) -> list[Line]:
    if data.startswith(b'krc1'):
        payload = bytes(byte ^ KRC_KEY[i % len(KRC_KEY)] for i, byte in enumerate(data[4:]))
        content = zlib.decompress(payload).decode('utf-8-sig')
    else:
        content = data.decode('utf-8-sig')
    lines: list[Line] = []
    for raw in content.splitlines():
        match = KRC_STAMP.match(raw.strip())
        if not match:
            continue
        start = int(match.group(1)) / 1000
        end = start + int(match.group(2)) / 1000
        body = match.group(3)
        words = [Word(token, start + int(at)/1000, start + (int(at)+int(length))/1000, False)
                 for at, length, _, token in KRC_WORD.findall(body) if token]
        clean = KRC_WORD.sub(lambda m: m.group(4), body)
        line = Line(clean, start, end, words, len(lines) % 2)
        if not words:
            line.estimate_words()
        lines.append(line)
    return lines


def parse_txt(content: str) -> list[Line]:
    lines = []
    for i, text in enumerate(x.strip() for x in content.splitlines() if x.strip()):
        line = Line(text, i * 4.0, i * 4.0 + 3.8, lane=i % 2)
        line.estimate_words()
        lines.append(line)
    return lines


def load_lyrics(path: str | Path) -> list[Line]:
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() == '.krc':
        return parse_krc(data)
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030', 'big5'):
        try:
            content = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('无法识别歌词编码')
    suffix = path.suffix.lower()
    if suffix == '.lrc':
        return parse_lrc(content)
    if suffix == '.ass':
        return parse_ass(content)
    if suffix == '.txt':
        return parse_txt(content)
    raise ValueError(f'不支持的歌词格式：{suffix}')
