"""
Blackmagic Camera Tooling Suite.
Modular toolkit for Auto Clip Transfer (Tool 1) and Batch Recording (Tool 2).
"""

from .camera_client import CameraClient
from .ftp_client import FtpClient
from .tool_auto_transfer import AutoTransferTool
from .tool_batch_recorder import BatchRecorderTool, DURATION_PRESETS

__all__ = [
    "CameraClient",
    "FtpClient",
    "AutoTransferTool",
    "BatchRecorderTool",
    "DURATION_PRESETS",
]
