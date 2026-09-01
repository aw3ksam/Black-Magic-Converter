"""
DaVinci Resolve Studio Process Manager and Scripting Client.
Handles environment configuration, headless background process launching, and API connection.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Any, Optional

from src.common.config import DaVinciConfig
from src.common.logger import setup_logger

logger = setup_logger("resolve_client")


def init_resolve_environment() -> None:
    """Configures macOS environment variables required by DaVinciResolveScript."""
    resolve_script_api = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
    resolve_script_lib = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

    os.environ["RESOLVE_SCRIPT_API"] = resolve_script_api
    os.environ["RESOLVE_SCRIPT_LIB"] = resolve_script_lib

    modules_path = os.path.join(resolve_script_api, "Modules")
    if modules_path not in sys.path:
        sys.path.append(modules_path)


class ResolveClient:
    """Manages connection and headless process lifecycle for DaVinci Resolve Studio."""

    def __init__(self, config: DaVinciConfig):
        self.config = config
        self._resolve: Optional[Any] = None
        self._process: Optional[subprocess.Popen] = None
        init_resolve_environment()

    def get_resolve_instance(self) -> Optional[Any]:
        """Attempts to connect to a running DaVinci Resolve instance."""
        try:
            import DaVinciResolveScript as dvr_script  # type: ignore
            resolve = dvr_script.scriptapp("Resolve")
            if resolve:
                return resolve
        except Exception as e:
            logger.debug(f"scriptapp('Resolve') attempt: {e}")
        return None

    def launch_headless_resolve(self) -> bool:
        """Launches DaVinci Resolve in background with -nogui parameter."""
        app_bin = Path(self.config.app_path)
        if not app_bin.exists():
            logger.error(f"DaVinci Resolve executable not found at: {app_bin}")
            return False

        logger.info(f"Launching headless DaVinci Resolve Studio: {app_bin} -nogui")
        try:
            self._process = subprocess.Popen(
                [str(app_bin), "-nogui"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to spawn headless Resolve process: {e}")
            return False

    def connect(self) -> Any:
        """
        Connects to DaVinci Resolve, launching headless mode if configured and necessary.
        Returns the native Resolve scripting object.
        """
        if self._resolve:
            return self._resolve

        logger.info("Connecting to DaVinci Resolve API...")
        resolve = self.get_resolve_instance()

        if resolve:
            logger.info("Connected to existing DaVinci Resolve instance.")
            self._resolve = resolve
            return self._resolve

        if not self.config.auto_start_headless:
            raise RuntimeError(
                "DaVinci Resolve is not running and auto_start_headless is disabled."
            )

        # Launch headless Resolve
        if not self.launch_headless_resolve():
            raise RuntimeError("Could not launch headless DaVinci Resolve.")

        start_time = time.time()
        logger.info(
            f"Waiting for DaVinci Resolve API to initialize (timeout: {self.config.launch_timeout}s)..."
        )

        while time.time() - start_time < self.config.launch_timeout:
            time.sleep(2.0)
            resolve = self.get_resolve_instance()
            if resolve:
                logger.info("Successfully connected to headless DaVinci Resolve!")
                self._resolve = resolve
                return self._resolve

        raise TimeoutError(
            f"Timed out after {self.config.launch_timeout}s waiting for DaVinci Resolve to initialize."
        )

    def close(self) -> None:
        """Closes connection and cleanly terminates headless process if managed."""
        if self._resolve:
            try:
                # Ask Resolve to quit gracefully through scripting API if supported
                if hasattr(self._resolve, "Quit"):
                    self._resolve.Quit()
            except Exception:
                pass
            self._resolve = None

        if self._process and self._process.poll() is None:
            logger.info("Closing headless DaVinci Resolve background process...")
            try:
                # Wait briefly for graceful exit after Quit()
                self._process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=3.0)
                except (subprocess.TimeoutExpired, Exception):
                    self._process.kill()
            self._process = None
            logger.info("Headless process stopped.")
