from __future__ import annotations
from array import array
import sys
from .export import binary


def load_peaks(path: str, columns: int = 5000) -> list[float]:
    import subprocess
    command = [binary('ffmpeg'), '-v', 'error', '-i', path, '-ac', '1', '-ar', '8000',
               '-f', 's16le', '-acodec', 'pcm_s16le', '-']
    result = subprocess.run(command, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    samples = array('h')
    samples.frombytes(result.stdout[:len(result.stdout) & ~1])
    if sys.byteorder != 'little':
        samples.byteswap()
    step = max(1, len(samples) // columns)
    return [max((abs(x) for x in samples[i:i+step]), default=0) / 32768 for i in range(0, len(samples), step)]
