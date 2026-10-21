import unittest
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from rks.gui import MainWindow
from rks.model import Project, Line, Word


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_preview_undo_and_drag(self):
        temporary = tempfile.TemporaryDirectory()
        window = MainWindow(recovery_path=Path(temporary.name)/'isolated_autosave.rks.json')
        window.project = Project(duration=4,lines=[Line('你好',0,2,[Word('你',0,1),Word('好',1,2)],0)])
        window._refresh_all()
        self.assertEqual(window.tree.topLevelItemCount(),1)
        self.assertEqual(window.export_progress.value(), 0)
        self.assertEqual([button.text() for button in window.export_buttons],
                         ['导出 ASS', '导出透明 MOV', '导出 PNG 序列', '导出预览 MP4'])
        window._snapshot()
        window._drag_word(0,0,.8,'end')
        self.assertAlmostEqual(window.project.lines[0].words[0].end,.8)
        window.undo()
        self.assertAlmostEqual(window.project.lines[0].words[0].end,1)
        window.tree.setCurrentItem(window.tree.topLevelItem(0).child(1))
        window.split_line()
        self.assertEqual([line.text for line in window.project.lines],['你','好'])
        window.karaoke_mode.setCurrentIndex(1)
        self.assertTrue(all(word.tag == 'k' for line in window.project.lines for word in line.words))
        window.layout_combo.setCurrentIndex(window.layout_combo.findData('stagger_left'))
        self.assertEqual(window.project.layout_mode, 'stagger_left')
        window.credit_edits['mv_director'].setText('测试导演')
        window._credit_edited('mv_director', '测试导演')
        self.assertEqual(window.project.credits.mv_director, '测试导演')
        self.assertIn('mv_director', window.project.credits.manual_fields)
        window.position=.5
        image = window.preview.grab().toImage()
        self.assertFalse(image.isNull())
        window.close()
        temporary.cleanup()

    def test_timeline_pan_and_traditional_conversion(self):
        with tempfile.TemporaryDirectory() as temporary:
            window = MainWindow(recovery_path=Path(temporary)/'isolated_autosave.rks.json')
            line = Line('我的头发', 140, 144,
                        [Word(char, 140+index, 141+index) for index, char in enumerate('我的头发')])
            window.project = Project(duration=300, lines=[line])
            window._refresh_all()
            window._set_zoom(60)
            self.assertGreater(window.timeline_scroll.maximum(), 0)
            window.timeline_scroll.setValue(130000)
            self.assertAlmostEqual(window.timeline.offset, 130, delta=.01)
            self.assertAlmostEqual(window.timeline.t_for(window.timeline.x_for(142)), 142, delta=.01)
            window.convert_traditional()
            self.assertEqual(window.project.lines[0].text, '我的頭髮')
            self.assertEqual([(word.start, word.end) for word in window.project.lines[0].words],
                             [(140,141),(141,142),(142,143),(143,144)])
            window.undo()
            self.assertEqual(window.project.lines[0].text, '我的头发')
            window.close()


if __name__ == '__main__':
    unittest.main()
