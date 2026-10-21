from pathlib import Path
import math
import struct
import wave
from rks.model import Project, Line, Word
from rks.ass import save_ass
from rks.export import export_video, alpha_samples, video_info

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / 'samples'
SAMPLE.mkdir(exist_ok=True)
rate = 44100
duration = 7
with wave.open(str(SAMPLE / 'demo.wav'), 'wb') as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(rate)
    frames = bytearray()
    for i in range(rate * duration):
        t = i / rate
        amp = .18 * (0.5 - .5 * math.cos(2 * math.pi * min(1, (t % 2) / .2)))
        value = int(32767 * amp * (math.sin(2 * math.pi * 220 * t) + .4 * math.sin(2 * math.pi * 330 * t)))
        frames += struct.pack('<h', max(-32768, min(32767, value)))
    wav.writeframes(frames)

def line(text, start, step, lane):
    words = [Word(char, start + i * step, start + (i + 1) * step) for i, char in enumerate(text)]
    return Line(text, start, start + len(text) * step + .45, words, lane)

project = Project(audio=str(SAMPLE / 'demo.wav'), duration=duration,
                  lines=[line('我的愛人再見', .6, .34, 0), line('留住這一刻', 3.45, .40, 1)])
project.save(SAMPLE / 'demo.rks.json')
save_ass(project, SAMPLE / 'demo.ass')
(SAMPLE / 'demo.lrc').write_text('[00:00.60]我的愛人再見\n[00:03.45]留住這一刻\n', encoding='utf-8')
out = export_video(project, SAMPLE / 'demo_alpha.mov')
print(video_info(str(out)))
print(alpha_samples(out, [.0, 1.2, 4.0]))
