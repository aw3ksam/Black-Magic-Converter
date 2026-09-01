"""
Unit Tests for DaVinci Resolve Project Manager and Render Pipeline with Mocks.
Verifies resolution matching (6K, 4K, 1080p), LUT assignment logic, and H.265 export settings.
"""

import unittest
from unittest.mock import MagicMock
from pathlib import Path

from src.common.config import TranscodeConfig, ColorConfig, AudioConfig
from src.dvr_engine.project_manager import ProjectManager, ClipInfo
from src.dvr_engine.render_pipeline import RenderPipeline


class MockMediaPoolItem:
    def __init__(self, properties):
        self._properties = properties

    def GetClipProperty(self, key=None):
        if key is None:
            return self._properties
        return self._properties.get(key, "")

    def GetAudioMapping(self):
        return '{"embedded_audio_channels": 2}'


class TestResolveEngineMocks(unittest.TestCase):

    def test_clip_inspection_6k(self):
        """Verify 6K BRAW metadata parsing."""
        mock_item = MockMediaPoolItem({
            "Resolution": "6144x3456",
            "FPS": "23.976",
            "Duration": "1420",
            "Camera Type": "Blackmagic Pocket Cinema Camera 6K Pro",
        })
        info = ProjectManager.inspect_media_clip(mock_item)
        self.assertEqual(info.width, 6144)
        self.assertEqual(info.height, 3456)
        self.assertEqual(info.fps, 23.976)
        self.assertEqual(info.audio_channels, 2)
        self.assertEqual(info.camera_type, "Blackmagic Pocket Cinema Camera 6K Pro")

    def test_clip_inspection_4k(self):
        """Verify 4K BRAW metadata parsing."""
        mock_item = MockMediaPoolItem({
            "Resolution": "4096x2160",
            "FPS": "24.0",
            "Duration": "850",
            "Camera Type": "Blackmagic URSA Mini Pro 4.6K G2",
        })
        info = ProjectManager.inspect_media_clip(mock_item)
        self.assertEqual(info.width, 4096)
        self.assertEqual(info.height, 2160)
        self.assertEqual(info.fps, 24.0)

    def test_clip_inspection_1080p(self):
        """Verify 1080p BRAW metadata parsing."""
        mock_item = MockMediaPoolItem({
            "Resolution": "1920x1080",
            "FPS": "60.0",
            "Duration": "300",
            "Camera Type": "Blackmagic Pocket Cinema Camera 4K",
        })
        info = ProjectManager.inspect_media_clip(mock_item)
        self.assertEqual(info.width, 1920)
        self.assertEqual(info.height, 1080)
        self.assertEqual(info.fps, 60.0)

    def test_render_pipeline_configuration(self):
        """Verify that render settings mirror 1:1 input resolution, Main10 H.265, and AAC audio."""
        mock_resolve = MagicMock()
        mock_project = MagicMock()
        mock_project.GetRenderFormats.return_value = {"mp4": "mp4", "mov": "mov"}
        mock_project.GetRenderCodecs.return_value = {"H.265 Main": "H265", "Apple HEVC": "H265_Apple"}
        mock_project.SetCurrentRenderFormatAndCodec.return_value = True
        mock_project.SetRenderSettings.return_value = True

        config = TranscodeConfig(
            container="mp4",
            codec="H265",
            encoding_profile="Main10",
            video_quality="Best",
            audio=AudioConfig(codec="aac", sample_rate=48000, bit_depth=16),
            color=ColorConfig(lut_path="Blackmagic Design/Blackmagic Gen 5 Film to Extended Video.cube"),
        )

        pipeline = RenderPipeline(resolve=mock_resolve, config=config)
        clip_6k = ClipInfo(width=6144, height=3456, fps=23.976, duration=1000)

        out_dir = Path("/tmp/test_output")
        success = pipeline.configure_render_settings(
            project=mock_project,
            clip_info=clip_6k,
            output_dir=out_dir,
            output_name="TEST_6K_CLIP",
        )

        self.assertTrue(success)
        mock_project.SetRenderSettings.assert_called_once()
        passed_settings = mock_project.SetRenderSettings.call_args[0][0]

        self.assertEqual(passed_settings["FormatWidth"], 6144)
        self.assertEqual(passed_settings["FormatHeight"], 3456)
        self.assertEqual(passed_settings["EncodingProfile"], "Main10")
        self.assertEqual(passed_settings["VideoQuality"], 0)
        self.assertEqual(passed_settings["AudioCodec"], "aac")
        self.assertEqual(passed_settings["CustomName"], "TEST_6K_CLIP")

    def test_lut_application_node(self):
        """Verify that LUT is applied to Node 1 of timeline clip item."""
        mock_resolve = MagicMock()
        mock_project = MagicMock()
        mock_resolve.GetProjectManager().GetCurrentProject.return_value = mock_project

        mock_timeline = MagicMock()
        mock_item = MagicMock()
        mock_item.GetNumNodes.return_value = 1
        mock_item.SetLUT.return_value = True
        mock_timeline.GetItemListInTrack.return_value = [mock_item]

        config = TranscodeConfig(
            color=ColorConfig(lut_path="Blackmagic Design/Blackmagic Gen 5 Film to Extended Video.cube")
        )
        pipeline = RenderPipeline(resolve=mock_resolve, config=config)
        clip_info = ClipInfo(width=3840, height=2160, fps=24.0, duration=500)

        success = pipeline.apply_lut(mock_timeline, clip_info)
        self.assertTrue(success)
        mock_item.SetLUT.assert_called_with(1, "Blackmagic Design/Blackmagic Gen 5 Film to Extended Video.cube")


if __name__ == "__main__":
    unittest.main()
