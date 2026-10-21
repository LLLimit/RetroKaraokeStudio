import tempfile
import unittest
from pathlib import Path

from rks.ass import generate_ass
from rks.layout import placements, visible_at
from rks.metadata import discover_credits
from rks.model import IntroCredits, Line, Project, Word


def demo_project(mode='stagger_left'):
    return Project(
        duration=8,
        layout_mode=mode,
        credits=IntroCredits(title='傷心太平洋', original_artist='任賢齊', lyricist='陳沒', duration=2),
        lines=[
            Line('第一句', 2, 4, [Word('第', 2, 2.5), Word('一', 2.5, 3), Word('句', 3, 4)]),
            Line('第二句', 4, 6, [Word('第', 4, 4.5), Word('二', 4.5, 5), Word('句', 5, 6)]),
            Line('第三句', 6, 8, [Word('第', 6, 6.5), Word('三', 6.5, 7), Word('句', 7, 8)]),
        ],
    )


class NewFeatureTests(unittest.TestCase):
    def test_stagger_left_promotes_next_line(self):
        project = demo_project()
        before = visible_at(project, 3)
        after = visible_at(project, 4.1)
        self.assertEqual([(x.line.text, x.karaoke, x.alignment) for x in before],
                         [('第一句', True, 1), ('第二句', False, 3)])
        self.assertEqual([(x.line.text, x.karaoke, x.alignment) for x in after],
                         [('第二句', True, 1), ('第三句', False, 3)])
        ass = generate_ass(project)
        self.assertIn('Dialogue: 2,0:00:00.00,0:00:02.00,Intro', ass)
        self.assertIn('傷心太平洋', ass)
        self.assertIn('原　唱：任賢齊', ass)
        self.assertIn('Upcoming', ass)
        self.assertIn(r'\an1\pos(', ass)
        self.assertIn(r'\an3\pos(', ass)

    def test_stagger_right_and_single(self):
        project = demo_project('stagger_right')
        self.assertEqual([(x.karaoke, x.alignment) for x in visible_at(project, 3)],
                         [(True, 3), (False, 1)])
        project.layout_mode = 'single'
        self.assertEqual(len(visible_at(project, 3)), 1)
        self.assertEqual(len(placements(project)), 3)

    def test_local_lyric_tags_and_manual_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            lyric = Path(temp) / 'demo.lrc'
            lyric.write_text('[ti:光輝歲月]\n[ar:BEYOND]\n[lyricist:黃家駒]\n[00:01.00]鐘聲響起歸家的訊號', encoding='utf-8')
            found = discover_credits('', str(lyric))
            self.assertEqual(found['title'][0], '光輝歲月')
            self.assertEqual(found['original_artist'][0], 'BEYOND')
            self.assertNotIn('mv_director', found)
            project = demo_project()
            project.credits.mv_director = '手動導演'
            project.credits.manual_fields.append('mv_director')
            project.save(Path(temp) / 'project.rks.json')
            loaded = Project.load(Path(temp) / 'project.rks.json')
            self.assertEqual(loaded.credits.mv_director, '手動導演')
            self.assertIn('mv_director', loaded.credits.manual_fields)


if __name__ == '__main__':
    unittest.main()
