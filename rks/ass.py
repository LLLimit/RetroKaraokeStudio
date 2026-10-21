from __future__ import annotations

from pathlib import Path
from .model import Project
from .layout import placements


def ass_color(hex_color: str) -> str:
    value = hex_color.lstrip('#')
    if len(value) != 6:
        raise ValueError(f'无效颜色：{hex_color}')
    return f'&H00{value[4:6]}{value[2:4]}{value[0:2]}'


def ass_timestamp(t: float) -> str:
    cs = max(0, round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f'{h}:{m:02d}:{s:02d}.{cs:02d}'


def escape(text: str) -> str:
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', r'\N')


def generate_ass(project: Project) -> str:
    style = project.style
    head = f'''[Script Info]
Title: Retro Karaoke Studio
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {project.width}
PlayResY: {project.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KTV,{style.font},{style.size},{ass_color(style.sung)},{ass_color(style.unsung)},{ass_color(style.outline)},&H80000000,-1,0,0,0,100,100,1,0,1,{style.outline_px},{style.shadow_px},2,64,64,{style.margin_bottom},1
Style: Upcoming,{style.font},{style.size},{ass_color(style.unsung)},{ass_color(style.unsung)},{ass_color(style.outline)},&H80000000,-1,0,0,0,100,100,1,0,1,{style.outline_px},{style.shadow_px},2,64,64,{style.margin_bottom},1
Style: Intro,{style.font},52,{ass_color('#1646D8')},{ass_color('#1646D8')},{ass_color('#FFFFFF')},&H80000000,-1,0,0,0,100,100,0,0,1,3,2,8,64,64,64,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    credits = project.credits
    intro_end = min(credits.duration, project.duration) if project.duration > 0 else credits.duration
    if credits.enabled and intro_end > 0:
        start_code = ass_timestamp(0)
        end_code = ass_timestamp(intro_end)
        center = project.width // 2
        if credits.title.strip():
            title_tag = '{\\an8\\pos(' + f'{center},{round(project.height*.24)}' + ')\\fs76\\fad(180,180)}'
            events.append(f'Dialogue: 2,{start_code},{end_code},Intro,,0,0,0,,{title_tag}{escape(credits.title.strip())}')
        labels = [('原　唱', credits.original_artist), ('作　詞', credits.lyricist),
                  ('作　曲', credits.composer), ('編　曲', credits.arranger), ('MV導演', credits.mv_director)]
        rows = [f'{name}：{value.strip()}' for name, value in labels if value.strip()]
        if rows:
            body_tag = '{\\an8\\pos(' + f'{center},{round(project.height*.38)}' + ')\\fs48\\fad(180,180)}'
            body = r'\N'.join(escape(row) for row in rows)
            events.append(f'Dialogue: 2,{start_code},{end_code},Intro,,0,0,0,,{body_tag}{body}')
    for item in placements(project):
        line = item.line
        start, end = max(0, item.start), max(0, item.end)
        if end <= start:
            continue
        tag = '{\\an' + str(item.alignment) + '\\pos(' + f'{item.x},{item.y}' + ')}'
        if not item.karaoke:
            events.append(f'Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},Upcoming,,0,0,0,,{tag}{escape(line.text)}')
            continue
        cursor = line.start
        for word in line.words:
            if word.start > cursor + .005:
                tag += r'{\k' + str(max(0, round((word.start-cursor)*100))) + '}'
            duration_cs = max(1, round((word.end - word.start) * 100))
            kind = word.tag if word.tag in ('k', 'kf', 'ko') else 'kf'
            tag += '{\\' + kind + str(duration_cs) + '}' + escape(word.text)
            cursor = word.end
        if not line.words:
            tag += escape(line.text)
        events.append(f'Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},KTV,,0,0,0,,{tag}')
    return head + '\n'.join(events) + '\n'


def save_ass(project: Project, path: str | Path) -> None:
    Path(path).write_text(generate_ass(project), encoding='utf-8-sig')
