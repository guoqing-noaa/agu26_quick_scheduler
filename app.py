#!/usr/bin/env python3
"""
app.py - 1-Click Launcher & Proxy for AGU Quick Scheduler
Starts a lightweight local HTTP server and automatically opens the schedule builder in your browser.
Includes a live Confex / m-anage API proxy to bypass browser CORS restrictions when fetching late-breaking talks.
"""

import http.server
import json
import os
import socket
import socketserver
import ssl
import sys
import urllib.parse
import urllib.request
import webbrowser

DEFAULT_PORT = 8081

def find_available_port(start_port=8081):
    for port in range(start_port, start_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port

class AppRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/fetch_confex" or parsed.path == "/api/fetch_agu":
            query = urllib.parse.parse_qs(parsed.query)
            endpoint = query.get("endpoint", [""])[0]
            if not endpoint:
                target_type = query.get("type", ["Paper"])[0]
                target_id = query.get("id", [""])[0]
                if target_id:
                    endpoint = f"{target_type}/{target_id}"

            if not endpoint:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"error": "Missing endpoint or id"}')
                return

            target_url = f"https://studio.m-anage.com/agu/agu26/meetingapi.cgi/{endpoint}"
            try:
                ctx = ssl._create_unverified_context()
                req = urllib.request.Request(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
                })
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        super().do_GET()

def main():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(workspace_dir)

    json_file = os.path.join(workspace_dir, "agu_program.json")
    if not os.path.exists(json_file):
        print("agu_program.json not found! Running fetcher first...")
        import fetch_agu_program
        fetch_agu_program.build_program_dataset()

    port = find_available_port(DEFAULT_PORT)
    url = f"http://localhost:{port}/"
    print("=" * 60)
    print("  AGU Quick Scheduler")
    print(f"  Local URL: {url}")
    print(f"  Live AGU API Proxy: http://localhost:{port}/api/fetch_confex")
    print("=" * 60)
    print("Opening browser... (Press Ctrl+C in this terminal to stop)\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    Handler = AppRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
