"""
Unified Command-Line Interface for BRAW Video Converter.
Supports background hot-folder monitoring, manual batch transcoding, LUT inspection, and environment diagnostics.
"""

import os
import sys
import time
import argparse
import signal
from pathlib import Path
from typing import Optional

from src.common.config import load_config, AppConfig
from src.common.logger import setup_logger
from src.common.watcher import FolderWatcher
from src.dvr_engine.resolve_client import ResolveClient
from src.dvr_engine.project_manager import ProjectManager
from src.dvr_engine.render_pipeline import RenderPipeline

logger = setup_logger("braw_cli")


def transcode_single_file(
    braw_path: Path,
    config: AppConfig,
    resolve_client: Optional[ResolveClient] = None,
    output_dir: Optional[Path] = None,
) -> bool:
    """Executes full transcode pipeline for a single BRAW clip."""
    logger.info(f"Starting transcode job for: {braw_path.name}")
    should_close_client = False

    if resolve_client is None:
        resolve_client = ResolveClient(config.davinci)
        should_close_client = True

    project_manager = None
    project = None
    project_name = f"{config.davinci.project_name_prefix}_{int(time.time())}_{braw_path.stem[:12]}"

    try:
        resolve = resolve_client.connect()
        project_manager = ProjectManager(resolve)
        project = project_manager.create_transcode_project(project_name)

        # Import clip & configure 1:1 timeline
        timeline, clip_info, _ = project_manager.import_and_setup_timeline(
            project=project,
            braw_file_path=braw_path,
            timeline_name=f"TL_{braw_path.stem}",
        )

        # Initialize Render Pipeline
        pipeline = RenderPipeline(resolve=resolve, config=config.transcode)

        # Apply Blackmagic 3D LUT
        pipeline.apply_lut(timeline=timeline, clip_info=clip_info)

        # Output folder
        dest_dir = output_dir or config.storage.completed_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        output_stem = braw_path.stem

        # Configure Render Settings
        if not pipeline.configure_render_settings(
            project=project,
            clip_info=clip_info,
            output_dir=dest_dir,
            output_name=output_stem,
        ):
            logger.error("Failed to configure render settings.")
            return False

        # Execute Render and Wait
        success = pipeline.render_and_wait(project=project)
        if success:
            logger.info(f"Transcode succeeded for {braw_path.name} -> {dest_dir / (output_stem + '.mp4')}")
        else:
            logger.error(f"Transcode failed for {braw_path.name}")
        return success

    except Exception as e:
        logger.exception(f"Transcode exception for {braw_path.name}: {e}")
        return False
    finally:
        if project and config.davinci.cleanup_projects_after_render and project_manager:
            try:
                project_manager.delete_project(project_name)
            except Exception:
                pass
        if should_close_client and resolve_client:
            resolve_client.close()


def cmd_watch(args):
    """Starts the hot-folder watcher daemon."""
    config = load_config(args.config)
    logger.info("Initializing BRAW Hot Folder Watcher...")
    logger.info(f"Ingest Hot Folder: {config.storage.ingest_dir}")
    logger.info(f"Output MP4 Folder: {config.storage.completed_dir}")
    logger.info(f"LUT: {config.transcode.color.lut_path}")
    logger.info(f"Codec: {config.transcode.codec} (Profile: {config.transcode.encoding_profile})")

    # Connect to DaVinci Resolve upfront
    resolve_client = ResolveClient(config.davinci)
    try:
        resolve_client.connect()
    except Exception as e:
        logger.warning(f"Could not connect to DaVinci Resolve on startup ({e}). Will attempt on first job.")

    def on_transcode(processing_braw_path: Path) -> bool:
        return transcode_single_file(
            braw_path=processing_braw_path,
            config=config,
            resolve_client=resolve_client,
        )

    watcher = FolderWatcher(config=config, transcode_callback=on_transcode)
    watcher.start()

    # Graceful shutdown handler
    def handle_sigint(signum, frame):
        logger.info("Shutdown signal received. Stopping watcher...")
        watcher.stop()
        resolve_client.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    logger.info("Hot Folder Watcher is running. Press Ctrl+C to exit.")
    while True:
        time.sleep(1.0)


def cmd_transcode(args):
    """Manually transcodes a file or directory."""
    config = load_config(args.config)
    target = Path(args.input_path).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else config.storage.completed_dir

    if not target.exists():
        logger.error(f"Input path does not exist: {target}")
        sys.exit(1)

    resolve_client = ResolveClient(config.davinci)
    resolve_client.connect()

    try:
        if target.is_file():
            success = transcode_single_file(
                braw_path=target,
                config=config,
                resolve_client=resolve_client,
                output_dir=output_dir,
            )
            sys.exit(0 if success else 1)
        elif target.is_dir():
            braw_files = list(target.glob("*.braw")) + list(target.glob("*.BRAW"))
            logger.info(f"Found {len(braw_files)} BRAW files in {target}")
            successes = 0
            for braw_file in braw_files:
                if transcode_single_file(
                    braw_path=braw_file,
                    config=config,
                    resolve_client=resolve_client,
                    output_dir=output_dir,
                ):
                    successes += 1
            logger.info(f"Completed batch transcode: {successes}/{len(braw_files)} succeeded.")
            sys.exit(0 if successes == len(braw_files) else 1)
    finally:
        resolve_client.close()


def cmd_list_luts(args):
    """Scans and lists installed Blackmagic 3D LUTs."""
    lut_dir = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/Blackmagic Design")
    print(f"\nScanning Blackmagic LUT directory: {lut_dir}\n" + "=" * 60)
    if lut_dir.exists():
        cube_files = sorted(list(lut_dir.glob("*.cube")))
        for idx, cube in enumerate(cube_files, 1):
            print(f"[{idx:02d}] {cube.name}")
        print(f"\nTotal Blackmagic LUTs found: {len(cube_files)}\n")
    else:
        print(f"Directory not found: {lut_dir}")


def cmd_test_env(args):
    """Diagnoses system requirements and environment setup."""
    print("\n" + "=" * 60)
    print(" BRAW Video Converter — Environment Diagnostics")
    print("=" * 60)

    # 1. Python Environment
    print(f"• Python Version: {sys.version.split()[0]} ({sys.executable})")

    # 2. DaVinci Resolve Application
    resolve_app = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
    resolve_bin = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve")
    print(f"• DaVinci Resolve App: {'FOUND' if resolve_app.exists() else 'MISSING'} ({resolve_app})")
    print(f"• DaVinci Resolve Binary: {'FOUND' if resolve_bin.exists() else 'MISSING'}")

    # 3. Scripting API Framework
    script_api = Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting")
    script_lib = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so")
    print(f"• Resolve Scripting API: {'FOUND' if script_api.exists() else 'MISSING'} ({script_api})")
    print(f"• Fusion Script Library: {'FOUND' if script_lib.exists() else 'MISSING'} ({script_lib})")

    # 4. Try importing DaVinciResolveScript
    sys.path.append(str(script_api / "Modules"))
    os.environ["RESOLVE_SCRIPT_API"] = str(script_api)
    os.environ["RESOLVE_SCRIPT_LIB"] = str(script_lib)
    try:
        import DaVinciResolveScript as dvr_script
        print("• DaVinciResolveScript Module: LOADED SUCCESSFULLY")
        resolve_instance = dvr_script.scriptapp("Resolve")
        print(f"• Active Resolve API Connection: {'CONNECTED' if resolve_instance else 'NOT RUNNING (Ready for headless launch)'}")
    except Exception as e:
        print(f"• DaVinciResolveScript Module: FAILED ({e})")

    # 5. FFmpeg and VideoToolbox
    ffmpeg_found = False
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"• FFmpeg (VideoToolbox): FOUND ({ffmpeg_path})")
    else:
        print("• FFmpeg: NOT FOUND in PATH")

    # 6. BRAW SDK Framework
    braw_fw = Path(__file__).parent.parent / "BRAW SDK" / "Blackmagic RAW SDK" / "Mac" / "Libraries" / "BlackmagicRawAPI.framework"
    print(f"• Native BRAW SDK Framework: {'FOUND' if braw_fw.exists() else 'MISSING'} ({braw_fw})")
    print("=" * 60 + "\n")


def main():
    # Base parent parser for shared arguments like --config
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("-c", "--config", type=str, default=None, help="Path to config.yaml")

    parser = argparse.ArgumentParser(
        description="BRAW to H.265 MP4 Automated Video Converter",
        parents=[config_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Watch command
    sub_watch = subparsers.add_parser("watch", parents=[config_parser], help="Start background hot folder watcher")
    sub_watch.set_defaults(func=cmd_watch)

    # Transcode command
    sub_trans = subparsers.add_parser("transcode", parents=[config_parser], help="Transcode a file or directory manually")
    sub_trans.add_argument("input_path", type=str, help="Path to .braw file or directory")
    sub_trans.add_argument("-o", "--output-dir", type=str, default=None, help="Custom output directory")
    sub_trans.set_defaults(func=cmd_transcode)

    # List LUTs command
    sub_luts = subparsers.add_parser("list-luts", parents=[config_parser], help="List available Blackmagic 3D LUTs")
    sub_luts.set_defaults(func=cmd_list_luts)

    # Diagnostics command
    sub_diag = subparsers.add_parser("test-env", parents=[config_parser], help="Run environment and API diagnostics")
    sub_diag.set_defaults(func=cmd_test_env)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
