from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float
    estimated: bool = False
    tag: str = 'kf'


@dataclass
class Line:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)
    lane: int = 0

    def estimate_words(self) -> None:
        chars = list(self.text)
        if not chars:
            self.words = []
            return
        weights = [0.45 if c.isspace() or c in '，。！？、,.!?' else 1.0 for c in chars]
        total = sum(weights)
        t = self.start
        self.words = []
        for c, w in zip(chars, weights):
            duration = max(0, self.end - self.start) * w / total
            self.words.append(Word(c, round(t, 4), round(t + duration, 4), True))
            t += duration
        self.words[-1].end = self.end


@dataclass
class Style:
    preset: str = '经典香港 KTV'
    font: str = 'Microsoft JhengHei'
    size: int = 62
    unsung: str = '#FFFFFF'
    sung: str = '#FFE03D'
    outline: str = '#000000'
    preview_background: str = '#000000'
    outline_px: float = 5.0
    shadow_px: float = 2.0
    margin_bottom: int = 78
    soft: bool = True


@dataclass
class IntroCredits:
    title: str = ''
    original_artist: str = ''
    lyricist: str = ''
    composer: str = ''
    arranger: str = ''
    mv_director: str = ''
    duration: float = 5.0
    enabled: bool = True
    manual_fields: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)


@dataclass
class Project:
    audio: str = ''
    lyrics_path: str = ''
    background_video: str = ''
    lines: list[Line] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    credits: IntroCredits = field(default_factory=IntroCredits)
    layout_mode: str = 'double'
    width: int = 1440
    height: int = 1080
    fps: int = 25
    duration: float = 0.0
    offset: float = 0.0
    path: str = ''

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.tmp')
        temp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(target)
        self.path = str(target)

    @classmethod
    def load(cls, path: str | Path) -> 'Project':
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        data['style'] = Style(**data.get('style', {}))
        data['credits'] = IntroCredits(**data.get('credits', {}))
        data['lines'] = [Line(**{**line, 'words': [Word(**word) for word in line.get('words', [])]}) for line in data.get('lines', [])]
        data['path'] = str(path)
        return cls(**data)

    def shift(self, seconds: float) -> None:
        for line in self.lines:
            line.start += seconds
            line.end += seconds
            for word in line.words:
                word.start += seconds
                word.end += seconds
        self.offset += seconds

    def normalize(self) -> None:
        self.lines.sort(key=lambda x: x.start)
        for i, line in enumerate(self.lines):
            line.lane = i % 2
            if not line.words:
                line.estimate_words()
        if self.lines and self.duration <= 0:
            self.duration = max(x.end for x in self.lines) + 1
