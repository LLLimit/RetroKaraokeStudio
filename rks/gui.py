from __future__ import annotations

import copy
from pathlib import Path
import tempfile
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QUrl, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QKeySequence, QShortcut, QImage
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox, QFormLayout, QFrame, QSlider,
    QColorDialog, QCheckBox, QLineEdit, QTabWidget, QScrollBar, QProgressBar)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from .model import Project, Line, Word, IntroCredits
from .importers import load_lyrics
from .ass import save_ass
from .layout import visible_at, LAYOUT_MODES
from .metadata import discover_credits, FIELDS
from .export import export_video, probe_duration, binary, alpha_samples, video_info
from .waveform import load_peaks
from .traditional import to_hong_kong_traditional
from .external_tools import find_audio_to_lyrics, bundled_installer, launch as launch_external_tool


PRESETS = {
    '经典香港 KTV': ('#FFFFFF', '#FFE03D', '#000000', 5, 2),
    '80 年代电视台': ('#D8E7FF', '#55ACFF', '#050D33', 5, 2),
    '90 年代 VHS': ('#F8F0E1', '#FFBD42', '#25101D', 6, 3),
    '纯白电影歌词': ('#C9C9C9', '#FFFFFF', '#000000', 3, 1),
}
CREDIT_LABELS = {'title': '歌名', 'original_artist': '原唱', 'lyricist': '作词',
                 'composer': '作曲', 'arranger': '编曲', 'mv_director': 'MV 导演'}


class Preview(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setMinimumSize(480, 350)
        self.reference = QImage()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#080c17'))
        box = QRectF(self.rect()).adjusted(16, 16, -16, -16)
        scale = min(box.width()/self.owner.project.width, box.height()/self.owner.project.height)
        w, h = self.owner.project.width*scale, self.owner.project.height*scale
        screen = QRectF(box.center().x()-w/2, box.center().y()-h/2, w, h)
        p.fillRect(screen, QColor('#171b27'))
        if not self.reference.isNull():
            p.drawImage(screen, self.reference)
        else:
            p.setPen(QColor('#38435a'))
            p.setFont(QFont('Segoe UI', 11))
            p.drawText(screen, Qt.AlignCenter, '4:3 · KTV PREVIEW')
        p.save()
        p.setClipRect(screen)
        s = self.owner.project.style
        now = self.owner.position
        for item in visible_at(self.owner.project, now):
            line = item.line
            font = QFont(s.font)
            font.setPixelSize(max(8, round(s.size*scale)))
            font.setBold(True)
            p.setFont(font)
            metrics = p.fontMetrics()
            widths = [metrics.horizontalAdvance(word.text) for word in line.words]
            x = screen.left() + item.x*scale
            if item.alignment == 2: x -= sum(widths)/2
            elif item.alignment == 3: x -= sum(widths)
            baseline = screen.top() + item.y*scale
            for word, width in zip(line.words, widths):
                if not item.karaoke:
                    color = QColor(s.unsung)
                elif now >= word.end:
                    color = QColor(s.sung)
                elif now <= word.start:
                    color = QColor(s.unsung)
                else:
                    # The app preview shows the same left-to-right fill used by ASS \kf.
                    progress = (now-word.start)/max(.001, word.end-word.start)
                    self._draw_text(p, x, baseline, word.text, QColor(s.unsung), s, scale)
                    p.save()
                    p.setClipRect(QRectF(x, baseline-metrics.ascent()-8, width*progress, metrics.height()+16))
                    self._draw_text(p, x, baseline, word.text, QColor(s.sung), s, scale)
                    p.restore()
                    x += width
                    continue
                self._draw_text(p, x, baseline, word.text, color, s, scale)
                x += width
        self._draw_intro(p, screen, scale)
        p.restore()
        p.setPen(QColor('#526078'))
        p.drawRect(screen)

    def _draw_text(self, p, x, y, text, color, style, scale):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addText(x, y, p.font(), text)
        p.fillPath(path.translated(style.shadow_px*scale, style.shadow_px*scale), QColor(0,0,0,125))
        p.strokePath(path, QPen(QColor(style.outline), max(1, style.outline_px*scale)))
        p.fillPath(path, color)

    def _draw_intro(self, p, screen, scale):
        from PySide6.QtGui import QPainterPath
        c = self.owner.project.credits
        now = self.owner.position
        if not c.enabled or now >= c.duration:
            return
        rows = [('原　唱', c.original_artist), ('作　詞', c.lyricist),
                ('作　曲', c.composer), ('編　曲', c.arranger), ('MV導演', c.mv_director)]
        entries = []
        if c.title.strip(): entries.append((c.title.strip(), .24, 76))
        for i, (label, value) in enumerate((label, value) for label, value in rows if value.strip()):
            entries.append((f'{label}：{value.strip()}', .38 + i*.056, 48))
        for text, y_fraction, px in entries:
            font = QFont(self.owner.project.style.font)
            font.setPixelSize(max(8, round(px*scale)))
            font.setBold(True)
            p.setFont(font)
            width = p.fontMetrics().horizontalAdvance(text)
            x = screen.center().x() - width/2
            y = screen.top() + self.owner.project.height*y_fraction*scale + p.fontMetrics().ascent()
            path = QPainterPath()
            path.addText(x, y, font, text)
            p.fillPath(path.translated(2*scale,2*scale), QColor(0,0,0,150))
            p.strokePath(path, QPen(QColor('#FFFFFF'), max(1,3*scale)))
            p.fillPath(path, QColor('#1646D8'))


class Timeline(QWidget):
    seek = Signal(float)
    edit_word = Signal(int, int, float, str)

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.peaks = []
        self.zoom = 1.0
        self.offset = 0.0
        self.drag = None
        self.setMinimumHeight(190)
        self.setMouseTracking(True)

    def seconds_per_width(self):
        return max(3.0, self.owner.project.duration / self.zoom)

    def max_offset(self):
        return max(0.0, self.owner.project.duration - self.seconds_per_width())

    def set_offset(self, value):
        self.offset = max(0.0, min(float(value), self.max_offset()))
        self.update()

    def x_for(self, t):
        return 60 + (t - self.offset) / self.seconds_per_width() * max(1, self.width()-80)

    def t_for(self, x):
        return max(0., min(self.owner.project.duration,
                           self.offset + (x-60)/max(1, self.width()-80) * self.seconds_per_width()))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#111827'))
        p.setPen(QColor('#71809a'))
        total = self.seconds_per_width()
        step = .5 if total <= 10 else 1 if total <= 30 else 5 if total <= 120 else 15
        t = max(0., int(self.offset / step) * step)
        while t <= min(self.owner.project.duration, self.offset + total):
            x = self.x_for(t)
            p.drawLine(int(x), 24, int(x), self.height()-8)
            p.drawText(int(x)+3, 17, f'{t:.1f}s' if step < 1 else f'{t:g}s')
            t += step
        if self.peaks:
            p.setPen(QPen(QColor('#21b7a5'), 1))
            for x in range(60, self.width()-20):
                i = int(self.t_for(x)/max(.1,self.owner.project.duration)*len(self.peaks))
                if i < len(self.peaks):
                    amp = self.peaks[i]
                    p.drawLine(x, int(72-amp*34), x, int(72+amp*34))
        for li, line in enumerate(self.owner.project.lines):
            y = 115 + line.lane * 32
            for wi, word in enumerate(line.words):
                a, b = self.x_for(word.start), self.x_for(word.end)
                if b < 60 or a > self.width():
                    continue
                rect = QRectF(max(60,a), y, max(2,min(self.width()-20,b)-max(60,a)), 25)
                p.fillRect(rect, QColor('#685c2a') if word.estimated else QColor('#276b86'))
                p.setPen(QColor('#d2e9f7'))
                p.drawText(rect.adjusted(3,0,-2,0), Qt.AlignVCenter, word.text)
                p.setPen(QColor('#d7f3ff'))
                if 60 <= b <= self.width()-20: p.drawLine(int(b), y, int(b), y+25)
        x = self.x_for(self.owner.position)
        p.setPen(QPen(QColor('#ff5d7c'), 2))
        if 60 <= x <= self.width()-20: p.drawLine(int(x), 23, int(x), self.height()-5)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.owner.timeline_scroll.setValue(self.owner.timeline_scroll.value() -
                                                round(delta / 120 * self.seconds_per_width() * 100))
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, e):
        x, y = e.position().x(), e.position().y()
        for li, line in enumerate(self.owner.project.lines):
            lane_y = 115 + line.lane*32
            if not lane_y <= y <= lane_y+25:
                continue
            for wi, word in enumerate(line.words):
                if abs(x-self.x_for(word.end)) < 8:
                    self.owner._snapshot()
                    self.drag = (li, wi, 'end')
                    return
                if abs(x-self.x_for(word.start)) < 8:
                    self.owner._snapshot()
                    self.drag = (li, wi, 'start')
                    return
        self.seek.emit(self.t_for(x))

    def mouseMoveEvent(self, e):
        if self.drag:
            li, wi, edge = self.drag
            self.edit_word.emit(li, wi, self.t_for(e.position().x()), edge)
        self.update()

    def mouseReleaseEvent(self, _):
        self.drag = None


class ExportThread(QThread):
    done = Signal(str)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, project, path, mode):
        super().__init__()
        self.project, self.path, self.mode = copy.deepcopy(project), path, mode

    def run(self):
        try:
            export_video(self.project, self.path, self.mode,
                         progress=lambda fraction: self.progress.emit(round(fraction * (95 if self.mode == 'prores' else 100))))
            if self.mode == 'prores':
                self.progress.emit(96)
                info = video_info(self.path)
                moment = min(self.project.duration-.05, self.project.lines[0].start+.5)
                samples = alpha_samples(self.path, [0., max(0.,moment)])
                if not info.get('pix_fmt','').startswith('yuva') or samples[0]['corner_alpha'] != 0 or samples[1]['visible_pixels'] == 0:
                    raise RuntimeError('透明度验证失败；请尝试 PNG 序列导出')
            self.progress.emit(100)
            self.done.emit(self.path)
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self, recovery_path: Path | None = None):
        super().__init__()
        self.project = Project()
        self.position = 0.
        self.history = []
        self.future = []
        self.updating = False
        self.worker = None
        self._loaded_audio = ''
        self._last_ref_bucket = -1
        self.setWindowTitle('Retro Karaoke Studio · 復古香港 KTV')
        self.resize(1500, 900)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._player_position)
        self._build()
        self._shortcuts()
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._tick)
        self.tick.start(40)
        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self._autosave)
        self.autosave.start(30000)
        self.recovery = recovery_path or (Path.home() / 'AppData' / 'Local' / 'RetroKaraokeStudio' / 'autosave.rks.json')
        if self.recovery.exists():
            try:
                self.project = Project.load(self.recovery)
                self._discover_credits()
                self.statusBar().showMessage('已恢复自动保存的项目', 7000)
            except Exception:
                pass

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12,12,12,12)
        top = QHBoxLayout()
        layout.addLayout(top)
        title = QLabel('RETRO <span style="color:#FFE03D">KARAOKE</span> STUDIO')
        title.setObjectName('title')
        top.addWidget(title)
        top.addStretch()
        self.export_buttons = []
        for label, fn in [('导入音乐', self.import_audio), ('识别歌词', self.open_audio_to_lyrics),
                          ('导入歌词', self.import_lyrics), ('打开项目', self.open_project),
                          ('保存', self.save_project), ('导出 ASS', self.export_ass), ('导出透明 MOV', lambda: self.export('prores')),
                          ('导出 PNG 序列', lambda: self.export('png')), ('导出预览 MP4', lambda: self.export('mp4'))]:
            button = QPushButton(label)
            button.clicked.connect(fn)
            top.addWidget(button)
            if label.startswith('导出'): self.export_buttons.append(button)
        progress_row = QHBoxLayout()
        self.export_status = QLabel('导出进度 · 等待导出')
        self.export_status.setMinimumWidth(170)
        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 100)
        self.export_progress.setValue(0)
        self.export_progress.setFormat('%p%')
        progress_row.addWidget(self.export_status)
        progress_row.addWidget(self.export_progress, 1)
        layout.addLayout(progress_row)
        main = QSplitter(Qt.Horizontal)
        layout.addWidget(main, 1)
        left = QFrame()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel('歌词 · 双击编辑时间 / 文本'))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['歌词 / 字', '开始', '结束', '来源'])
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(0, 128)
        self.tree.setColumnWidth(1, 62)
        self.tree.setColumnWidth(2, 62)
        self.tree.itemChanged.connect(self._tree_changed)
        ll.addWidget(self.tree)
        row = QHBoxLayout()
        for label, fn in [('+ 加一句', self.add_line), ('拆分句', self.split_line), ('删除', self.delete_line), ('逐字估时', self.estimate_selected), ('转繁体', self.convert_traditional)]:
            b = QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        ll.addLayout(row)
        main.addWidget(left)
        center = QWidget(); cl = QVBoxLayout(center)
        preview_head = QHBoxLayout(); preview_head.addWidget(QLabel('节目监视器 · 4:3'))
        bg = QPushButton('载入参考视频'); bg.clicked.connect(self.import_background); preview_head.addWidget(bg)
        preview_head.addStretch(); cl.addLayout(preview_head)
        self.preview = Preview(self); cl.addWidget(self.preview, 1)
        transport = QHBoxLayout()
        self.play_button = QPushButton('▶ 播放'); self.play_button.clicked.connect(self.toggle_play); transport.addWidget(self.play_button)
        tap = QPushButton('T 逐字打点'); tap.clicked.connect(self.tap_word); transport.addWidget(tap)
        self.time_label = QLabel('00:00.00'); transport.addWidget(self.time_label); transport.addStretch()
        cl.addLayout(transport)
        self.timeline = Timeline(self); self.timeline.seek.connect(self.seek); self.timeline.edit_word.connect(self._drag_word)
        cl.addWidget(self.timeline)
        zoom_row = QHBoxLayout(); zoom_row.addWidget(QLabel('时间轴缩放'))
        zoom = QSlider(Qt.Horizontal); zoom.setRange(10,100); zoom.setValue(10)
        zoom.valueChanged.connect(lambda v: self._set_zoom(v)); zoom_row.addWidget(zoom)
        cl.addLayout(zoom_row)
        scroll_row = QHBoxLayout(); scroll_row.addWidget(QLabel('时间轴位置'))
        self.timeline_scroll = QScrollBar(Qt.Horizontal)
        self.timeline_scroll.setObjectName('timelinePosition')
        self.timeline_scroll.valueChanged.connect(self._scroll_timeline)
        scroll_row.addWidget(self.timeline_scroll)
        cl.addLayout(scroll_row)
        main.addWidget(center)
        right = QFrame(); rl = QVBoxLayout(right)
        rl.addWidget(QLabel('字幕设计 / 片头'))
        tabs = QTabWidget()
        style_tab = QWidget()
        form = QFormLayout()
        style_tab.setLayout(form)
        self.layout_combo = QComboBox()
        for label, value in [('单行 · 居中', 'single'), ('双行 · 底部交替', 'double'),
                             ('双列 · 左上当前', 'stagger_left'), ('双列 · 右下当前', 'stagger_right')]:
            self.layout_combo.addItem(label, value)
        self.layout_combo.currentIndexChanged.connect(self._layout_changed)
        form.addRow('歌词显示', self.layout_combo)
        self.preset = QComboBox(); self.preset.addItems([*PRESETS, '自定义']); self.preset.currentTextChanged.connect(self.apply_preset)
        form.addRow('预设', self.preset)
        self.font = QFontComboBox(); self.font.setCurrentFont(QFont(self.project.style.font)); self.font.currentFontChanged.connect(lambda f: self._style('font', f.family()))
        form.addRow('中文字体', self.font)
        self.size = QSpinBox(); self.size.setRange(20,180); self.size.setValue(self.project.style.size); self.size.valueChanged.connect(lambda v: self._style('size', v)); form.addRow('字号', self.size)
        self.outline = QDoubleSpinBox(); self.outline.setRange(0,15); self.outline.setValue(self.project.style.outline_px); self.outline.valueChanged.connect(lambda v: self._style('outline_px', v)); form.addRow('描边 px', self.outline)
        self.shadow = QDoubleSpinBox(); self.shadow.setRange(0,15); self.shadow.setValue(self.project.style.shadow_px); self.shadow.valueChanged.connect(lambda v: self._style('shadow_px', v)); form.addRow('阴影 px', self.shadow)
        self.margin = QSpinBox(); self.margin.setRange(0,300); self.margin.setValue(self.project.style.margin_bottom); self.margin.valueChanged.connect(lambda v: self._style('margin_bottom', v)); form.addRow('底部安全距', self.margin)
        self.karaoke_mode = QComboBox(); self.karaoke_mode.addItems(['平滑填充 · kf','整字切换 · k','描边切换 · ko'])
        self.karaoke_mode.currentIndexChanged.connect(self._set_karaoke_mode); form.addRow('唱字动画', self.karaoke_mode)
        self.soft = QCheckBox('轻微电视柔化'); self.soft.setChecked(self.project.style.soft)
        self.soft.toggled.connect(lambda value: self._style('soft',value)); form.addRow('画面处理',self.soft)
        self.color_buttons = {}
        for label, attr in [('未唱颜色', 'unsung'), ('已唱颜色', 'sung'), ('描边颜色', 'outline'), ('MP4 背景', 'preview_background')]:
            button = QPushButton(getattr(self.project.style, attr)); button.clicked.connect(lambda _, a=attr, b=button: self._color(a,b)); form.addRow(label, button)
            self.color_buttons[attr] = button
        self.resolution = QComboBox(); self.resolution.addItems(['1440 × 1080 · 25 fps', '1920 × 1080 · 30 fps']); self.resolution.currentIndexChanged.connect(self._resolution); form.addRow('画幅', self.resolution)
        self.offset = QDoubleSpinBox(); self.offset.setRange(-600,600); self.offset.setDecimals(2); self.offset.setSingleStep(.05); self.offset.valueChanged.connect(self._offset); form.addRow('整体偏移 s', self.offset)
        tabs.addTab(style_tab, '歌词样式')
        credit_tab = QWidget()
        credit_form = QFormLayout(credit_tab)
        self.credit_enabled = QCheckBox('显示复古片头')
        self.credit_enabled.setChecked(self.project.credits.enabled)
        self.credit_enabled.toggled.connect(self._intro_enabled)
        credit_form.addRow('片头', self.credit_enabled)
        self.credit_duration = QDoubleSpinBox()
        self.credit_duration.setRange(0, 30)
        self.credit_duration.setDecimals(1)
        self.credit_duration.setSingleStep(.5)
        self.credit_duration.setValue(self.project.credits.duration)
        self.credit_duration.valueChanged.connect(self._intro_duration)
        credit_form.addRow('时长 s', self.credit_duration)
        self.credit_edits = {}
        for label, field in [('歌名', 'title'), ('原唱', 'original_artist'), ('作词', 'lyricist'),
                             ('作曲', 'composer'), ('编曲', 'arranger'), ('MV 导演', 'mv_director')]:
            edit = QLineEdit()
            edit.setPlaceholderText('自动读取或手动填写')
            edit.editingFinished.connect(lambda f=field, e=edit: self._credit_edited(f, e.text()))
            credit_form.addRow(label, edit)
            self.credit_edits[field] = edit
        scan = QPushButton('重新解析本地标签')
        scan.clicked.connect(self._discover_credits)
        credit_form.addRow(scan)
        self.credit_hint = QLabel('优先读取音乐和歌词标签；没有的字段请手动填写。')
        self.credit_hint.setWordWrap(True)
        credit_form.addRow(self.credit_hint)
        tabs.addTab(credit_tab, '片头信息')
        rl.addWidget(tabs, 1)
        note = QLabel('黄色 = 估算逐字时间\n蓝色 = 原始 / 手工时间\n拖动区块边界或按 T 精修')
        note.setWordWrap(True); note.setObjectName('note'); rl.addWidget(note)
        main.addWidget(right)
        main.setSizes([340, 850, 290])
        self.setStyleSheet('''
            QMainWindow,QWidget{background:#0c111d;color:#e7edf7;font:13px "Segoe UI"}
            QFrame{background:#121a29;border:1px solid #253148;border-radius:8px}
            QLabel{border:0;background:transparent} QLabel#title{font-size:21px;font-weight:800;letter-spacing:2px}
            QLabel#note{color:#899bb5;line-height:1.5}
            QPushButton{background:#202d43;border:1px solid #364762;border-radius:5px;padding:7px 10px;color:#f2f6ff}
            QPushButton:hover{background:#344968;border-color:#e7c655}
            QTreeWidget,QComboBox,QSpinBox,QDoubleSpinBox,QFontComboBox,QLineEdit{background:#101827;color:#e9f2ff;border:1px solid #35425a;padding:5px}
            QTabWidget::pane{border:1px solid #253148} QTabBar::tab{background:#1b283a;padding:8px 16px} QTabBar::tab:selected{background:#314663;color:#FFE03D}
            QTreeWidget::item:selected{background:#355d79} QHeaderView::section{background:#25354a;color:#c8d6ea;padding:5px}
            QSplitter::handle{background:#0a0f19;width:8px}
            QSlider::groove:horizontal{height:8px;background:#182337;border:1px solid #354b67;border-radius:4px}
            QSlider::sub-page:horizontal{background:#2F6D99;border-radius:4px}
            QSlider::handle:horizontal{background:#4DA9E8;border:2px solid #A7D9F7;width:18px;height:18px;margin:-7px 0;border-radius:10px}
            QSlider::handle:horizontal:hover{background:#83C8F2;border-color:#E2F5FF}
            QScrollBar#timelinePosition:horizontal{height:18px;background:#182337;border:1px solid #354b67;border-radius:7px}
            QScrollBar#timelinePosition::handle:horizontal{background:#4DA9E8;min-width:32px;border:2px solid #A7D9F7;border-radius:7px}
            QScrollBar#timelinePosition::handle:horizontal:hover{background:#83C8F2}
            QScrollBar#timelinePosition::add-line:horizontal,QScrollBar#timelinePosition::sub-line:horizontal{width:0px}
            QScrollBar#timelinePosition::add-page:horizontal,QScrollBar#timelinePosition::sub-page:horizontal{background:transparent}
            QProgressBar{background:#182337;border:1px solid #354b67;border-radius:5px;text-align:center;color:#e7edf7;min-height:18px}
            QProgressBar::chunk{background:#4DA9E8;border-radius:4px}
        ''')

    def _shortcuts(self):
        for key, fn in [('Space', self.toggle_play), ('T', self.tap_word), ('Ctrl+Z', self.undo), ('Ctrl+Y', self.redo), ('Ctrl+S', self.save_project)]:
            shortcut = QShortcut(QKeySequence(key), self); shortcut.activated.connect(fn)

    def _snapshot(self):
        self.history.append(copy.deepcopy(self.project.to_dict()))
        self.history = self.history[-60:]
        self.future.clear()

    def _restore(self, data):
        from .model import Style
        self.project = Project(**{**data, 'style': Style(**data['style']),
                                  'credits': IntroCredits(**data.get('credits', {})),
                                  'lines': [Line(**{**line, 'words':[Word(**w) for w in line['words']]}) for line in data['lines']]})
        self._refresh_all()

    def undo(self):
        if self.history:
            self.future.append(copy.deepcopy(self.project.to_dict()))
            self._restore(self.history.pop())

    def redo(self):
        if self.future:
            self.history.append(copy.deepcopy(self.project.to_dict()))
            self._restore(self.future.pop())

    def _refresh_all(self):
        self.updating = True
        self.tree.clear()
        for li, line in enumerate(self.project.lines):
            item = QTreeWidgetItem([line.text, f'{line.start:.2f}', f'{line.end:.2f}', '句'])
            item.setData(0, Qt.UserRole, (li,-1))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.tree.addTopLevelItem(item)
            for wi, word in enumerate(line.words):
                child = QTreeWidgetItem([word.text, f'{word.start:.2f}', f'{word.end:.2f}', '估算' if word.estimated else '精确'])
                child.setData(0, Qt.UserRole, (li,wi))
                child.setFlags(child.flags() | Qt.ItemIsEditable)
                if word.estimated: child.setForeground(3, QColor('#e8c75c'))
                item.addChild(child)
        self.font.setCurrentFont(QFont(self.project.style.font))
        self.size.setValue(self.project.style.size); self.outline.setValue(self.project.style.outline_px)
        self.shadow.setValue(self.project.style.shadow_px); self.margin.setValue(self.project.style.margin_bottom)
        self.soft.setChecked(self.project.style.soft)
        for attr, button in self.color_buttons.items(): button.setText(getattr(self.project.style, attr))
        first_word = next((line.words[0] for line in self.project.lines if line.words), None)
        self.karaoke_mode.setCurrentIndex({'kf':0,'k':1,'ko':2}.get(first_word.tag if first_word else 'kf',0))
        layout_index = self.layout_combo.findData(self.project.layout_mode)
        self.layout_combo.setCurrentIndex(max(0, layout_index))
        self.credit_enabled.setChecked(self.project.credits.enabled)
        self.credit_duration.setValue(self.project.credits.duration)
        for field, edit in self.credit_edits.items():
            edit.setText(getattr(self.project.credits, field))
            edit.setToolTip(self.project.credits.sources.get(field, '未解析到；可手动填写'))
        missing = [CREDIT_LABELS[field] for field in FIELDS if not getattr(self.project.credits, field)]
        self.credit_hint.setText('未解析到：' + '、'.join(missing) + '。可手动填写；重新解析会保留手动字段。' if missing else '片头信息已填写；可继续修改。')
        self.offset.setValue(self.project.offset)
        self.updating = False
        self._sync_timeline_scroll()
        if self.project.audio and Path(self.project.audio).exists() and self.project.audio != self._loaded_audio:
            self.player.setSource(QUrl.fromLocalFile(self.project.audio))
            try: self.timeline.peaks = load_peaks(self.project.audio)
            except Exception: self.timeline.peaks = []
            self._loaded_audio = self.project.audio
        self.preview.update(); self.timeline.update()

    def _tree_changed(self, item, column):
        if self.updating: return
        ref = item.data(0, Qt.UserRole)
        if not ref: return
        li, wi = ref
        if li >= len(self.project.lines): return
        target = self.project.lines[li] if wi < 0 else self.project.lines[li].words[wi]
        try:
            value = item.text(column) if column == 0 else float(item.text(column))
        except ValueError:
            self._refresh_all(); return
        if column <= 2:
            self._snapshot()
            setattr(target, ['text','start','end'][column], value)
            if wi >= 0: target.estimated = False
            if wi < 0 and column == 0: target.estimate_words()
            self._refresh_all()

    def _drag_word(self, li, wi, value, edge):
        word = self.project.lines[li].words[wi]
        if edge == 'start': word.start = max(self.project.lines[li].start, min(value, word.end-.01))
        else: word.end = min(self.project.lines[li].end, max(value, word.start+.01))
        word.estimated = False
        self.timeline.update(); self.preview.update()
        self.updating = True
        child = self.tree.topLevelItem(li).child(wi)
        if child:
            child.setText(1, f'{word.start:.2f}'); child.setText(2, f'{word.end:.2f}'); child.setText(3,'精确')
        self.updating = False

    def import_audio(self):
        path,_ = QFileDialog.getOpenFileName(self,'选择音乐','','音频 (*.wav *.mp3 *.flac *.m4a *.aac *.ogg);;所有文件 (*)')
        if not path: return
        self._snapshot(); self.project.audio = path
        try: self.project.duration = probe_duration(path)
        except Exception as e: QMessageBox.warning(self,'音频错误',str(e)); return
        self._discover_credits()
        self._refresh_all()

    def open_audio_to_lyrics(self):
        tool = find_audio_to_lyrics()
        if tool is None:
            installer = bundled_installer()
            if installer is None:
                QMessageBox.information(self, '需要 AudioToLyrics',
                    '未找到 AudioToLyrics。请从其官方 GitHub 项目安装后，再点击“识别歌词”。\n'
                    'https://github.com/huqiu0313/AudioToLyrics')
                return
            answer = QMessageBox.question(self, '安装 AudioToLyrics',
                '组合包附有 AudioToLyrics 作者发布的原版安装程序。\n'
                '首次使用请先安装，完成后再点“识别歌词”。现在启动安装程序吗？')
            if answer != QMessageBox.Yes:
                return
            tool = installer
        try:
            if self.project.audio and tool != bundled_installer():
                QApplication.clipboard().setText(self.project.audio)
                self.statusBar().showMessage('已复制当前音乐路径；请在 AudioToLyrics 中添加文件，生成后点“导入歌词”', 15000)
            launch_external_tool(tool)
        except OSError as error:
            QMessageBox.warning(self, '启动失败', str(error))

    def import_lyrics(self):
        path,_ = QFileDialog.getOpenFileName(self,'选择歌词','','歌词 (*.lrc *.krc *.ass *.txt)')
        if not path: return
        try: lines = load_lyrics(path)
        except Exception as e: QMessageBox.warning(self,'歌词错误',str(e)); return
        self._snapshot(); self.project.lines = lines; self.project.lyrics_path = path
        self.project.normalize(); self._discover_credits(); self._refresh_all()

    def import_background(self):
        path,_ = QFileDialog.getOpenFileName(self,'选择参考视频','','视频 (*.mp4 *.mov *.mkv *.avi)')
        if not path: return
        self.project.background_video = path
        self._reference_frame()

    def _reference_frame(self):
        if not self.project.background_video: return
        self._last_ref_bucket = int(self.position * 4)
        try:
            import subprocess
            result = subprocess.run([binary('ffmpeg'),'-v','error','-ss',str(self.position),'-i',self.project.background_video,
                                     '-frames:v','1','-f','image2pipe','-vcodec','png','-'], capture_output=True,
                                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            image = QImage.fromData(result.stdout, 'PNG')
            if not image.isNull(): self.preview.reference = image; self.preview.update()
        except Exception: pass

    def add_line(self):
        self._snapshot()
        start = self.position
        line = Line('新歌词',start,start+3,lane=len(self.project.lines)%2)
        line.estimate_words(); self.project.lines.append(line); self.project.normalize(); self._refresh_all()

    def split_line(self):
        item = self.tree.currentItem()
        if not item: return
        li, wi = item.data(0, Qt.UserRole)
        line = self.project.lines[li]
        if len(line.words) < 2: return
        cut = wi if wi > 0 else len(line.words)//2
        if cut <= 0 or cut >= len(line.words): return
        self._snapshot()
        later = line.words[cut:]
        new_line = Line(''.join(word.text for word in later),later[0].start,line.end,later,(line.lane+1)%2)
        line.words = line.words[:cut]
        line.text = ''.join(word.text for word in line.words)
        line.end = line.words[-1].end
        self.project.lines.insert(li+1,new_line)
        self.project.normalize(); self._refresh_all()

    def delete_line(self):
        item = self.tree.currentItem()
        if not item: return
        li, wi = item.data(0, Qt.UserRole)
        self._snapshot()
        if wi < 0: self.project.lines.pop(li)
        else:
            line = self.project.lines[li]; line.words.pop(wi); line.text = ''.join(w.text for w in line.words)
        self._refresh_all()

    def estimate_selected(self):
        item = self.tree.currentItem()
        if item:
            li,_ = item.data(0, Qt.UserRole)
            self._snapshot(); self.project.lines[li].estimate_words(); self._refresh_all()

    def convert_traditional(self):
        if not self.project.lines: return
        self._snapshot()
        for line in self.project.lines:
            source = ''.join(word.text for word in line.words) if line.words else line.text
            converted = to_hong_kong_traditional(source, line.words)
            line.text, line.words = converted
        self._refresh_all()
        self.statusBar().showMessage('歌词已转换为香港繁体；可用 Ctrl+Z 撤销', 7000)

    def tap_word(self):
        item = self.tree.currentItem()
        if not item: return
        li,wi = item.data(0, Qt.UserRole)
        if wi < 0:
            if not self.project.lines[li].words: return
            wi = 0
        self._snapshot()
        word = self.project.lines[li].words[wi]
        word.start = self.position
        word.estimated = False
        if wi > 0:
            previous = self.project.lines[li].words[wi-1]
            previous.end = max(previous.start+.01, self.position)
            previous.estimated = False
        has_next = self.tree.topLevelItem(li).child(wi+1) is not None
        self._refresh_all()
        if has_next: self.tree.setCurrentItem(self.tree.topLevelItem(li).child(wi+1))

    def seek(self, seconds):
        self.position = min(max(0.,seconds),max(seconds,self.project.duration))
        if self.project.audio: self.player.setPosition(round(self.position*1000))
        self._keep_playhead_visible()
        self.preview.update(); self.timeline.update()
        if self.project.background_video: self._reference_frame()

    def toggle_play(self):
        if not self.project.audio: return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause(); self.play_button.setText('▶ 播放')
        else:
            self.player.play(); self.play_button.setText('Ⅱ 暂停')

    def _player_position(self, ms):
        self.position = ms/1000
        self._keep_playhead_visible()
        self.time_label.setText(f'{int(self.position//60):02}:{self.position%60:05.2f}')
        self.preview.update(); self.timeline.update()

    def _tick(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState and self.project.background_video:
            if int(self.position*4) != self._last_ref_bucket: self._reference_frame()

    def _set_zoom(self, value):
        self.timeline.zoom = 1 + (value-10)/10
        self.timeline.set_offset(self.position - self.timeline.seconds_per_width() * .3)
        self._sync_timeline_scroll()

    def _scroll_timeline(self, value):
        self.timeline.set_offset(value / 1000)

    def _sync_timeline_scroll(self):
        span = self.timeline.seconds_per_width()
        maximum = round(self.timeline.max_offset() * 1000)
        self.timeline_scroll.blockSignals(True)
        self.timeline_scroll.setRange(0, maximum)
        self.timeline_scroll.setPageStep(max(1, round(span * 1000)))
        self.timeline_scroll.setSingleStep(max(100, round(span * 100)))
        self.timeline.set_offset(self.timeline.offset)
        self.timeline_scroll.setValue(round(self.timeline.offset * 1000))
        self.timeline_scroll.blockSignals(False)

    def _keep_playhead_visible(self):
        span = self.timeline.seconds_per_width()
        if self.position < self.timeline.offset or self.position > self.timeline.offset + span * .88:
            self.timeline.set_offset(self.position - span * .2)
            self._sync_timeline_scroll()

    def _layout_changed(self, index):
        if self.updating or index < 0: return
        mode = self.layout_combo.itemData(index)
        if mode != self.project.layout_mode:
            self._snapshot()
            self.project.layout_mode = mode
            self.preview.update()

    def _intro_enabled(self, checked):
        if self.updating: return
        self._snapshot()
        self.project.credits.enabled = checked
        self.preview.update()

    def _intro_duration(self, seconds):
        if self.updating: return
        self._snapshot()
        self.project.credits.duration = seconds
        self.preview.update()

    def _credit_edited(self, field, text):
        if self.updating: return
        value = text.strip()
        if value == getattr(self.project.credits, field): return
        self._snapshot()
        setattr(self.project.credits, field, value)
        if field not in self.project.credits.manual_fields:
            self.project.credits.manual_fields.append(field)
        self.project.credits.sources[field] = '手动填写'
        self._refresh_all()

    def _discover_credits(self, _checked=False):
        try:
            found = discover_credits(self.project.audio, self.project.lyrics_path)
        except Exception as error:
            self.statusBar().showMessage(f'本地标签解析失败：{error}；可手动填写', 9000)
            return
        credits = self.project.credits
        for field in FIELDS:
            if field in credits.manual_fields and getattr(credits, field).strip(): continue
            value, source = found.get(field, ('', ''))
            setattr(credits, field, value)
            if source: credits.sources[field] = source
            else: credits.sources.pop(field, None)
        self._refresh_all()
        self.statusBar().showMessage(f'已从本地解析 {len(found)} 项片头信息；缺失项可手动编辑', 7000)

    def _style(self, key, value):
        if self.updating: return
        setattr(self.project.style,key,value); self.preview.update()

    def _color(self, attr, button):
        color = QColorDialog.getColor(QColor(getattr(self.project.style, attr)),self)
        if color.isValid(): setattr(self.project.style,attr,color.name().upper()); button.setText(color.name().upper()); self.preview.update()

    def apply_preset(self, name):
        if self.updating or name not in PRESETS: return
        values = PRESETS[name]
        s = self.project.style; s.preset = name
        s.unsung,s.sung,s.outline,s.outline_px,s.shadow_px = values
        self._refresh_all()

    def _set_karaoke_mode(self, index):
        if self.updating: return
        self._snapshot()
        kind = ['kf','k','ko'][index]
        for line in self.project.lines:
            for word in line.words: word.tag = kind
        self.preview.update()

    def _resolution(self, index):
        if self.updating: return
        self.project.width,self.project.height,self.project.fps = (1440,1080,25) if index == 0 else (1920,1080,30)
        self.preview.update()

    def _offset(self, value):
        if self.updating: return
        delta = value - self.project.offset
        self.project.shift(delta); self._refresh_all()

    def open_project(self):
        path,_ = QFileDialog.getOpenFileName(self,'打开项目','','Retro Karaoke 项目 (*.json)')
        if path:
            try: self.project = Project.load(path); self._discover_credits()
            except Exception as e: QMessageBox.warning(self,'打开失败',str(e))

    def save_project(self):
        path = self.project.path
        if not path or path == str(self.recovery):
            path,_ = QFileDialog.getSaveFileName(self,'保存项目','','Retro Karaoke 项目 (*.rks.json)')
        if path:
            try: self.project.save(path); self.statusBar().showMessage(f'已保存：{path}',5000)
            except Exception as e: QMessageBox.warning(self,'保存失败',str(e))

    def _autosave(self):
        if self.project.lines or self.project.audio:
            original = self.project.path
            try: self.project.save(self.recovery)
            finally: self.project.path = original

    def export_ass(self):
        path,_ = QFileDialog.getSaveFileName(self,'导出 ASS','','ASS 字幕 (*.ass)')
        if path:
            try: save_ass(self.project,path); self.statusBar().showMessage(f'已导出：{path}',7000)
            except Exception as e: QMessageBox.warning(self,'导出失败',str(e))

    def export(self, mode):
        if self.worker and self.worker.isRunning(): return
        if not self.project.lines: QMessageBox.information(self,'缺少歌词','请先导入歌词'); return
        if mode == 'png': path = QFileDialog.getExistingDirectory(self,'选择 PNG 序列目录')
        else:
            suffix = '.mov' if mode == 'prores' else '.mp4'
            path,_ = QFileDialog.getSaveFileName(self,'导出视频','',f'视频 (*{suffix})')
        if not path: return
        if mode == 'png': path = str(Path(path)/'karaoke_png')
        self.export_progress.setValue(0)
        self.export_status.setText('导出进度 · 正在渲染')
        for button in self.export_buttons: button.setEnabled(False)
        self.worker = ExportThread(self.project,path,mode)
        self.worker.progress.connect(self._export_progress_update)
        self.worker.done.connect(self._export_done)
        self.worker.failed.connect(self._export_failed)
        self.worker.start()
        self.statusBar().showMessage('正在后台渲染…')

    def _export_progress_update(self, value):
        self.export_progress.setValue(value)
        if value >= 96 and self.worker and self.worker.mode == 'prores':
            self.export_status.setText('导出进度 · 正在验证透明通道')

    def _export_done(self, path):
        self.export_progress.setValue(100)
        self.export_status.setText('导出进度 · 已完成')
        for button in self.export_buttons: button.setEnabled(True)
        self.statusBar().showMessage(f'导出完成：{path}', 10000)
        QMessageBox.information(self, '导出完成', path)

    def _export_failed(self, error):
        self.export_status.setText('导出进度 · 失败')
        for button in self.export_buttons: button.setEnabled(True)
        QMessageBox.warning(self, '导出失败', error)

    def closeEvent(self,event):
        self._autosave()
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self,'正在导出','请等待当前导出完成')
            event.ignore()
        else: event.accept()
