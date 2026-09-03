#!/usr/bin/env python3
"""
Blackmagic Camera Tooling Suite Runner.
Starts the embedded dashboard and API server for Tool 1 (Auto Transfer) and Tool 2 (Batch Recorder).
"""

import argparse
import logging
from pathlib import Path
import sys

from bm_camera.server import start_server


def main():
    parser = argparse.ArgumentParser(description="Blackmagic Camera Tooling Suite (PYXIS 6K)")
    parser.add_argument("--camera-ip", default="192.168.8.133", help="Camera IP address (default: 192.168.8.133)")
    parser.add_argument("--ftp-host", default=None, help="Camera FTP host (default: matches camera IP)")
    parser.add_argument("--port", type=int, default=8080, help="Web dashboard server port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Web dashboard bind address (default: 0.0.0.0)")
    parser.add_argument("--dest-dir", default="./transfers", help="Local download directory (default: ./transfers)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    static_dir = Path(__file__).resolve().parent / "dashboard"
    transfers_dir = Path(args.dest_dir).resolve()
    transfers_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" Blackmagic Camera Tooling Suite")
    print(f" - Camera IP:     {args.camera_ip}")
    print(f" - FTP Host:      {args.ftp_host or args.camera_ip}")
    print(f" - Download Dir:  {transfers_dir}")
    print(f" - Dashboard UI:  http://localhost:{args.port}")
    print("=" * 70)

    server = start_server(
        host=args.host,
        port=args.port,
        camera_ip=args.camera_ip,
        ftp_host=args.ftp_host,
        dest_dir=str(transfers_dir),
        static_dir=static_dir,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
