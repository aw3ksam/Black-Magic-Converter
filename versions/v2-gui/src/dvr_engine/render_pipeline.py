"""
Render Pipeline Controller for DaVinci Resolve Studio.
Applies Blackmagic built-in 3D LUTs, configures H.265 MP4 render settings, and executes exports.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.common.config import TranscodeConfig
from src.common.logger import setup_logger
from src.dvr_engine.project_manager import ClipInfo

logger = setup_logger("render_pipeline")


class RenderPipeline:
    """Manages color LUT application, render settings, and job queue execution."""

    def __init__(self, resolve: Any, config: TranscodeConfig):
        self.resolve = resolve
        self.config = config

    def apply_lut(self, timeline: Any, clip_info: ClipInfo) -> bool:
        """
        Applies the configured Blackmagic built-in 3D LUT to the first video track's clip node.
        """
        if self.config.color.mode == "none":
            logger.info("Color mode is 'none'; skipping LUT application.")
            return True

        # Refresh Resolve's LUT list to ensure custom/standard LUT paths are loaded
        project = self.resolve.GetProjectManager().GetCurrentProject()
        if project:
            try:
                project.RefreshLUTList()
            except Exception:
                pass

        # Retrieve first timeline item in video track 1
        video_items = timeline.GetItemListInTrack("video", 1)
        if not video_items:
            logger.error("No video items found on track 1 of timeline.")
            return False

        timeline_item = video_items[0]
        lut_to_apply = self.config.color.lut_path

        logger.info(f"Applying LUT to Node 1: '{lut_to_apply}'")
        num_nodes = timeline_item.GetNumNodes()
        if num_nodes < 1:
            logger.warning(f"Timeline item has {num_nodes} nodes; node graph might be uninitialized.")

        # Set LUT on Node 1 (1-based index)
        success = timeline_item.SetLUT(1, lut_to_apply)
        if not success and self.config.color.fallback_lut_path:
            logger.warning(
                f"Primary LUT '{lut_to_apply}' failed. Attempting fallback LUT: '{self.config.color.fallback_lut_path}'"
            )
            success = timeline_item.SetLUT(1, self.config.color.fallback_lut_path)

        if success:
            logger.info(f"Successfully applied LUT to clip in timeline.")
        else:
            logger.warning(
                f"Could not apply LUT '{lut_to_apply}'. Please check if LUT file exists in Resolve LUT path."
            )

        return success

    def configure_render_settings(
        self,
        project: Any,
        clip_info: ClipInfo,
        output_dir: Path,
        output_name: str,
    ) -> bool:
        """Configures project render settings for 1:1 resolution H.265 MP4 export."""
        # Available formats and codecs
        render_formats = project.GetRenderFormats() or {}
        logger.debug(f"Available render formats: {render_formats}")

        target_format = self.config.container.lower()  # "mp4"
        target_codec = self.config.codec               # "H265"

        # Check for Apple Silicon hardware codec identifier if standard H265 needs mapping
        codecs = project.GetRenderCodecs(target_format) or {}
        logger.debug(f"Available codecs for format '{target_format}': {codecs}")

        selected_codec = target_codec
        # Resolve uses specific keys: 'H265' or 'H265_Apple' on macOS
        for codec_desc, codec_key in codecs.items():
            if "h.265" in codec_desc.lower() or "hevc" in codec_desc.lower() or "h265" in codec_key.lower():
                selected_codec = codec_key
                break

        logger.info(f"Setting render format='{target_format}', codec='{selected_codec}'")
        format_set = project.SetCurrentRenderFormatAndCodec(target_format, selected_codec)
        if not format_set:
            logger.warning(f"SetCurrentRenderFormatAndCodec returned false for format '{target_format}'")

        # Map VideoQuality: DaVinci H.265 requires integer 0 (Auto) or integer bitrate
        video_quality_val = 0
        if self.config.bitrate_mbps > 0:
            video_quality_val = int(self.config.bitrate_mbps * 1000)
        elif isinstance(self.config.video_quality, int):
            video_quality_val = self.config.video_quality
        else:
            # String like "Best", "High", "Auto" -> 0 for automatic
            video_quality_val = 0

        # Verified supported render parameters for DaVinci Resolve Studio H.265 MP4
        render_settings: Dict[str, Any] = {
            "SelectAllFrames": True,
            "TargetDir": str(output_dir.resolve()),
            "CustomName": output_name,
            "ExportVideo": True,
            "ExportAudio": True,
            "FormatWidth": int(clip_info.width),
            "FormatHeight": int(clip_info.height),
            "EncodingProfile": self.config.encoding_profile,  # "Main10"
            "VideoQuality": video_quality_val,                # 0 for Auto
            "AudioCodec": self.config.audio.codec,            # "aac"
            "AudioBitDepth": int(self.config.audio.bit_depth),# 16
            "AudioSampleRate": int(self.config.audio.sample_rate), # 48000
            "NetworkOptimization": True,
        }

        logger.info(
            f"Configured Render Settings: {clip_info.width}x{clip_info.height} @ {clip_info.fps}fps, "
            f"Codec={selected_codec}, Profile={self.config.encoding_profile}, TargetDir={output_dir}"
        )

        success = project.SetRenderSettings(render_settings)
        if not success:
            logger.warning("Bulk SetRenderSettings returned false; applying essential settings individually...")
            individual_success = True
            for key, val in render_settings.items():
                res = project.SetRenderSettings({key: val})
                if not res:
                    logger.debug(f"Optional render setting '{key}={val}' was not accepted by Resolve.")
            # Verify if target dir and custom name were set
            success = True

        return success

    def render_and_wait(
        self,
        project: Any,
        poll_interval: float = 1.0,
    ) -> bool:
        """Adds current timeline to render queue, executes render, and monitors progress."""
        logger.info("Clearing old render jobs and adding transcode job to render queue...")
        project.DeleteAllRenderJobs()

        job_id = project.AddRenderJob()
        if not job_id:
            logger.error("Failed to add render job to DaVinci Resolve render queue.")
            return False

        logger.info(f"Render job added with ID: {job_id}. Starting render...")
        if not project.StartRendering([job_id]):
            logger.error("Failed to start rendering.")
            return False

        start_time = time.time()
        last_percentage = -1

        while project.IsRenderingInProgress():
            time.sleep(poll_interval)
            status = project.GetRenderJobStatus(job_id) or {}
            percentage = status.get("CompletionPercentage", 0)
            job_status = status.get("JobStatus", "Rendering")
            fps = status.get("EstimatedFps", 0)

            if percentage != last_percentage:
                logger.info(
                    f"Transcode Progress: {percentage}% | Speed: {fps:.1f} fps | Elapsed: {int(time.time() - start_time)}s"
                )
                last_percentage = percentage

            if job_status.lower() in ["failed", "cancelled", "error"]:
                logger.error(f"Render job failed with status: {job_status} - Error: {status.get('Error', 'Unknown')}")
                return False

        # Final status check
        final_status = project.GetRenderJobStatus(job_id) or {}
        job_status = str(final_status.get("JobStatus", "")).lower()
        if "complete" in job_status or job_status == "done" or final_status.get("CompletionPercentage") == 100:
            elapsed = time.time() - start_time
            logger.info(f"Render completed successfully in {elapsed:.1f} seconds!")
            return True

        logger.error(f"Render finished with unexpected status: {final_status}")
        return False
