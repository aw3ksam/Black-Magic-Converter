"""
Project and Media Pool Manager for DaVinci Resolve.
Handles dynamic project creation, media pool ingestion, clip inspection, and 1:1 timeline creation.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.common.logger import setup_logger

logger = setup_logger("project_manager")


class ClipInfo:
    """Encapsulates extracted metadata properties of an ingested BRAW clip."""

    def __init__(
        self,
        width: int,
        height: int,
        fps: float,
        duration: int,
        camera_type: str = "Unknown",
        audio_channels: int = 2,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = duration
        self.camera_type = camera_type
        self.audio_channels = audio_channels

    def __repr__(self) -> str:
        return f"<ClipInfo {self.width}x{self.height} @ {self.fps}fps, Camera: {self.camera_type}>"


class ProjectManager:
    """Manages project setup, clip ingestion, and timeline configuration."""

    def __init__(self, resolve: Any):
        self.resolve = resolve
        self.project_manager = resolve.GetProjectManager()

    def create_transcode_project(self, project_name: str) -> Any:
        """Creates or loads a designated transcode project."""
        logger.info(f"Opening/Creating transcode project: {project_name}")
        project = self.project_manager.LoadProject(project_name)
        if not project:
            project = self.project_manager.CreateProject(project_name)
        if not project:
            raise RuntimeError(f"Failed to create/load project '{project_name}' in DaVinci Resolve.")
        return project

    def delete_project(self, project_name: str) -> bool:
        """Deletes a transient transcode project after completion."""
        try:
            return self.project_manager.DeleteProject(project_name)
        except Exception as e:
            logger.warning(f"Could not delete project '{project_name}': {e}")
            return False

    @staticmethod
    def inspect_media_clip(media_item: Any) -> ClipInfo:
        """Extracts resolution, frame rate, and camera metadata from MediaPoolItem."""
        properties = media_item.GetClipProperty() or {}
        logger.debug(f"MediaPoolItem Raw Properties: {properties}")

        # Width & Height
        width = 1920
        height = 1080

        # Try discrete width/height or parse from 'Resolution' string (e.g. '6144x3456')
        if "Resolution" in properties and "x" in str(properties["Resolution"]):
            parts = str(properties["Resolution"]).split("x")
            try:
                width = int(parts[0].strip())
                height = int(parts[1].strip())
            except ValueError:
                pass
        elif "Width" in properties and "Height" in properties:
            try:
                width = int(properties["Width"])
                height = int(properties["Height"])
            except ValueError:
                pass

        # Frame rate
        fps = 24.0
        if "FPS" in properties:
            try:
                fps = float(properties["FPS"])
            except ValueError:
                pass

        # Duration
        duration = 0
        if "Duration" in properties:
            try:
                duration = int(properties["Duration"])
            except ValueError:
                pass

        # Camera Type / Model
        camera_type = str(properties.get("Camera Type", properties.get("Camera", "Blackmagic")))

        # Audio channels
        audio_channels = 2
        try:
            mapping_str = media_item.GetAudioMapping()
            if mapping_str and "embedded_audio_channels" in str(mapping_str):
                import json
                mapping = json.loads(mapping_str)
                audio_channels = int(mapping.get("embedded_audio_channels", 2))
        except Exception:
            pass

        clip_info = ClipInfo(
            width=width,
            height=height,
            fps=fps,
            duration=duration,
            camera_type=camera_type,
            audio_channels=audio_channels,
        )
        logger.info(f"Extracted Clip Metadata: {clip_info}")
        return clip_info

    def import_and_setup_timeline(
        self,
        project: Any,
        braw_file_path: Path,
        timeline_name: str = "Transcode_Timeline",
    ) -> Tuple[Any, ClipInfo, Any]:
        """
        Imports the BRAW file into the Media Pool, configures project resolution to match 1:1,
        and creates a single-clip timeline.
        """
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()

        logger.info(f"Importing BRAW media into Resolve Media Pool: {braw_file_path.name}")
        imported_items = media_pool.ImportMedia([str(braw_file_path.resolve())])

        if not imported_items:
            raise RuntimeError(f"MediaPool.ImportMedia failed for file: {braw_file_path}")

        media_item = imported_items[0]
        clip_info = self.inspect_media_clip(media_item)

        # Configure Project Timeline Resolution to match source 1:1
        logger.info(
            f"Configuring project timeline resolution to 1:1 source: {clip_info.width}x{clip_info.height} @ {clip_info.fps}fps"
        )
        project.SetSetting("timelineResolutionWidth", str(clip_info.width))
        project.SetSetting("timelineResolutionHeight", str(clip_info.height))
        project.SetSetting("timelineFrameRate", str(clip_info.fps))

        # Create Timeline from Clip
        timeline = media_pool.CreateTimelineFromClips(timeline_name, [media_item])
        if not timeline:
            raise RuntimeError(f"Failed to create timeline from clip: {braw_file_path.name}")

        # Also configure Timeline-specific settings if override is supported
        try:
            timeline.SetSetting("useCustomSettings", "1")
            timeline.SetSetting("timelineResolutionWidth", str(clip_info.width))
            timeline.SetSetting("timelineResolutionHeight", str(clip_info.height))
            timeline.SetSetting("timelineFrameRate", str(clip_info.fps))
        except Exception as e:
            logger.debug(f"Timeline-level setting override notice: {e}")

        logger.info(f"Successfully created timeline '{timeline_name}' matching {clip_info.width}x{clip_info.height}")
        return timeline, clip_info, media_item
