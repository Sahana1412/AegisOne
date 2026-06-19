"""
MCP Filesystem Adapter – safe filesystem operations for incident response.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

QUARANTINE_DIR = os.getenv("QUARANTINE_DIR", "/tmp/aegisone_quarantine")


class FilesystemAdapter:
    def __init__(self) -> None:
        Path(QUARANTINE_DIR).mkdir(parents=True, exist_ok=True)

    async def quarantine_file(self, file_path: str) -> dict[str, Any]:
        """Move a suspicious file to the quarantine directory."""
        source = Path(file_path)
        if not source.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        dest = Path(QUARANTINE_DIR) / f"{source.name}.quarantined"
        try:
            shutil.move(str(source), str(dest))
            logger.info("Quarantined file: %s -> %s", source, dest)
            return {"success": True, "original_path": file_path, "quarantine_path": str(dest)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_log_file(self, file_path: str, max_lines: int = 1000) -> dict[str, Any]:
        """Read a log file safely."""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"success": False, "error": "File not found"}
            with open(path) as f:
                lines = f.readlines()
            return {
                "success": True,
                "lines": lines[-max_lines:],
                "total_lines": len(lines),
                "path": file_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_directory(self, dir_path: str) -> dict[str, Any]:
        """List directory contents."""
        try:
            path = Path(dir_path)
            if not path.is_dir():
                return {"success": False, "error": "Not a directory"}
            contents = [
                {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                }
                for item in sorted(path.iterdir())
            ]
            return {"success": True, "contents": contents}
        except Exception as e:
            return {"success": False, "error": str(e)}
