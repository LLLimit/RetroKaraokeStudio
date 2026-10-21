import tempfile
import unittest
import zlib
import subprocess
from pathlib import Path

from rks.model import Project, Line, Word
from rks.importers import parse_lrc, parse_ass, parse_krc, KRC_KEY
from rks.ass import generate_ass
from rks.export import alpha_samples, export_video, video_info, binary


class CoreTests(unittest.TestCase):
    def test_plain_lrc_is_estimated(self):
        lines = parse_lrc('[00:01.00]你好世界\n[00:03.00]再見\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].end, 3)
        self.assertTrue(all(w.estimated for w in lines[0].words))
        self.assertAlmostEqual(lines[0].words[-1].end, 3)

    def test_enhanced_lrc_precise(self):
        lines = parse_lrc('[00:01.00]<00:01.00>你<00:01.50>好\n[00:03.00]再見')
        self.assertEqual([w.start for w in lines[0].words], [1, 1.5])
        self.assertTrue(all(not w.estimated for w in lines[0].words))

    def test_ass_roundtrip_and_lanes(self):
        project = Project(lines=[Line('你好',0,1.5,[Word('你',0,.5,False,'k'),Word('好',.5,1,False,'ko')],0),
                                 Line('再見',2,3,[Word('再',2,2.5),Word('見',2.5,3)],1)])
        source = generate_ass(project)
        self.assertIn(r'{\k50}你', source)
        self.assertIn(r'{\ko50}好', source)
        self.assertIn(r'{\kf50}再', source)
        parsed = parse_ass(source)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].words[1].tag, 'ko')
        self.assertEqual([x.lane for x in parsed], [0,1])

    def test_krc_plain(self):
        lines = parse_krc('[1000,1000]<0,500,0>你<500,500,0>好'.encode())
        self.assertEqual([w.text for w in lines[0].words], ['你','好'])
        self.assertEqual(lines[0].words[1].start, 1.5)

    def test_krc_encoded(self):
        body = zlib.compress('[1000,1000]<0,500,0>你<500,500,0>好'.encode())
        encoded = b'krc1' + bytes(b ^ KRC_KEY[i % len(KRC_KEY)] for i,b in enumerate(body))
        self.assertEqual(parse_krc(encoded)[0].text,'你好')

    def test_project_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'test.rks.json'
            project = Project(lines=parse_lrc('[00:01.00]繁體字'))
            project.save(p)
            self.assertEqual(Project.load(p).lines[0].text, '繁體字')

    def test_alpha_and_mp4(self):
        project = Project(width=320,height=240,fps=25,duration=1.5,
                          lines=[Line('繁體',.1,1.3,[Word('繁',.1,.6),Word('體',.6,1.2)],0)])
        project.style.size=40
        with tempfile.TemporaryDirectory() as td:
            mov = export_video(project,Path(td)/'alpha.mov')
            info = video_info(str(mov))
            self.assertEqual(info['codec_name'],'prores')
            self.assertIn('yuva',info['pix_fmt'])
            samples = alpha_samples(mov,[0,.5])
            self.assertEqual(samples[0]['corner_alpha'],0)
            self.assertEqual(samples[0]['visible_pixels'],0)
            self.assertGreater(samples[1]['visible_pixels'],0)
            project.style.preview_background = '#203060'
            mp4 = export_video(project,Path(td)/'preview.mp4','mp4')
            self.assertEqual(video_info(str(mp4))['codec_name'],'h264')
            rgb = subprocess.run([binary('ffmpeg'),'-v','error','-i',str(mp4),'-frames:v','1','-f','rawvideo',
                                  '-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
            self.assertGreater(rgb[2],rgb[0])
            frames = export_video(project,Path(td)/'png','png')
            self.assertGreater(len(list(frames.glob('frame_*.png'))),10)

    def test_export_progress(self):
        project = Project(width=320,height=240,fps=25,duration=1,
                          lines=[Line('進度',.1,.9,[Word('進',.1,.5),Word('度',.5,.9)])])
        values = []
        with tempfile.TemporaryDirectory() as td:
            export_video(project, Path(td)/'progress.mov', progress=values.append)
        self.assertTrue(values)
        self.assertEqual(values[-1], 1.0)
        self.assertTrue(all(0 <= value <= 1 for value in values))


if __name__ == '__main__':
    unittest.main()
