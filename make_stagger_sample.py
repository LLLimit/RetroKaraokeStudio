"""Create an original synthetic sample showing the title card and staggered lyrics."""
from pathlib import Path
import math
import struct
import wave

from rks.ass import save_ass
from rks.export import alpha_samples, export_video, video_info
from rks.model import IntroCredits, Line, Project, Word

sample = Path(__file__).resolve().parent / 'samples'
sample.mkdir(exist_ok=True)
audio = sample / 'stagger_demo.wav'
rate, seconds = 22050, 7
with wave.open(str(audio), 'wb') as sound:
    sound.setnchannels(1)
    sound.setsampwidth(2)
    sound.setframerate(rate)
    frames = bytearray()
    for index in range(rate * seconds):
        t = index / rate
        amp = 0.11 * math.sin(2 * math.pi * (220 if t < 3.5 else 330) * t)
        frames.extend(struct.pack('<h', int(32767 * amp)))
    sound.writeframes(frames)


def line(text, start, step):
    words = [Word(char, start + index * step, start + (index + 1) * step)
             for index, char in enumerate(text)]
    return Line(text, start, start + len(text) * step, words)


project = Project(
    audio=str(audio), duration=seconds, layout_mode='stagger_left',
    credits=IntroCredits(title='霓虹之夜', original_artist='示例歌手', lyricist='示例作詞',
                         composer='示例作曲', arranger='示例編曲', mv_director='示例導演', duration=2),
    lines=[line('今夜霓虹閃爍', 2.25, .27), line('讓歌聲留在心中', 4.25, .26)],
)
project.save(sample / 'stagger_demo.rks.json')
save_ass(project, sample / 'stagger_demo.ass')
mov = export_video(project, sample / 'stagger_demo_alpha.mov')
print(video_info(str(mov)))
print(alpha_samples(mov, [0, .8, 2.8, 4.8]))
