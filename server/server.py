#!/usr/bin/env python3
"""
Video Script Analyzer - API Server (重构版)
分层架构：handlers → services → repository → config

启动: python server/server.py
访问: http://localhost:8840
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持直接运行 python server/server.py）
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json
from urllib.parse import urlparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

from server.config import PORT, WEB_DIR
from server.handlers import library, pipeline, analyze, tags, import_video, files
from server.handlers.files import handle_static


class APIHandler(SimpleHTTPRequestHandler):
    """HTTP 路由分发器 — 薄层，只做路由 + 参数解析。"""

    def do_GET(self):
        self.parsed = urlparse(self.path)
        path = self.parsed.path

        try:
            if path == "/":
                files.handle_index(self)
            elif path == "/api/library":
                library.handle_get_library(self)
            elif path == "/api/stats":
                library.handle_stats(self)
            elif path == "/api/methodology":
                library.handle_methodology(self)
            elif path == "/api/tags":
                tags.handle_get(self)
            elif path == "/api/progress":
                pipeline.handle_progress(self)
            elif path == "/api/scan-videos":
                import_video.handle_scan(self)
            elif path.startswith("/api/video-file/"):
                files.handle_video_file(self)
            elif path.startswith("/api/video/"):
                files.handle_video_resource(self)
            elif path.startswith("/sounds/"):
                files.handle_sound(self)
            elif path.startswith("/css/") or path.startswith("/js/") or path.startswith("/assets/"):
                handle_static(self)
            else:
                self.send_error(404, "Not found")
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            self._send_json_error({"error": str(e)}, 500)

    def do_POST(self):
        self.parsed = urlparse(self.path)
        path = self.parsed.path
        body = self._parse_body()

        try:
            if path == "/api/process":
                pipeline.handle_process(self, body)
            elif path == "/api/download":
                pipeline.handle_download(self, body)
            elif path == "/api/transcribe":
                pipeline.handle_transcribe(self, body)
            elif path == "/api/analyze":
                analyze.handle_analyze(self, body)
            elif path == "/api/batch-analyze":
                analyze.handle_batch(self, body)
            elif path == "/api/save":
                library.handle_save(self, body)
            elif path == "/api/delete":
                library.handle_delete(self, body)
            elif path == "/api/tags":
                tags.handle_post(self, body)
            elif path == "/api/import":
                import_video.handle_import(self, body)
            else:
                self.send_error(404, "Not found")
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            self._send_json_error({"error": str(e)}, 500)

    def _parse_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw else {}
        return {}

    def _send_json_error(self, data, status=500):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, format, *args):
        pass  # 静默默认日志


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器，支持并发请求（进度轮询 + 管道执行）。"""
    daemon_threads = True


def main():
    print("=" * 60)
    print("  Video Script Analyzer Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Data: {WEB_DIR.parent / 'data'}")
    print("=" * 60)

    import os
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("  ⚠ DEEPSEEK_API_KEY 未设置，AI 分析功能不可用")
        print("  → 设置方式: set DEEPSEEK_API_KEY=sk-xxx")

    print("  Ctrl+C to stop")
    print("=" * 60)

    server = ThreadedHTTPServer(("0.0.0.0", PORT), APIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
