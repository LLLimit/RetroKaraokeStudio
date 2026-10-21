import sys
import json
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from rks.gui import MainWindow


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--self-check':
        from rks.model import Project, Line, Word
        from rks.export import binary, export_video, video_info, alpha_samples
        from rks.traditional import to_hong_kong_traditional
        with tempfile.TemporaryDirectory() as directory:
            project = Project(width=320, height=240, fps=25, duration=1.2,
                              lines=[Line('繁體', .1, 1., [Word('繁', .1, .5), Word('體', .5, .9)])])
            project.style.size = 40
            video = export_video(project, Path(directory) / 'check.mov')
            result = {'ffmpeg': binary('ffmpeg'), 'ffprobe': binary('ffprobe'),
                      'video': video_info(str(video)), 'alpha': alpha_samples(video, [0., .5]),
                      'traditional': to_hong_kong_traditional('我的头发', [])[0]}
            Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName('Retro Karaoke Studio')
    icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'icon.png'
    app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
