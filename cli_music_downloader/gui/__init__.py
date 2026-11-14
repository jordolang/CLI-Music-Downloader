"""
Desktop music app: library browser and player, playlists, tag editing and organizing,
plus search with song/video previews and one-click downloads into the library.

The UI is a web page served from 127.0.0.1 and shown in a native window (pywebview);
without pywebview it opens in the default browser instead.
"""

import logging
import sys
import threading
import time
import webbrowser
from typing import Optional


def run_gui(library: Optional[str] = None, port: int = 0, browser: bool = False, verbose: bool = False) -> int:
    from .server import App, make_server

    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = App(library)
    server = make_server(app, port)
    # The token rides in the URL fragment: browsers never send it to the server, and the
    # served page contains no secret for other programs on this Mac to read.
    url = f"http://127.0.0.1:{server.server_address[1]}/#t={app.token}"
    app.start_background()
    threading.Thread(target=server.serve_forever, daemon=True, name="http").start()

    webview = None
    if not browser:
        try:
            import webview  # noqa: F811
        except ImportError:
            print("ℹ️  pywebview is not installed (pip install pywebview); opening in your browser instead.",
                  file=sys.stderr)
    if webview is not None:
        app.window = webview.create_window(
            "CLI Music", url, width=1380, height=880, min_size=(980, 620), background_color="#16161a",
            text_select=False)
        webview.start(private_mode=False, debug=verbose)
        server.shutdown()
        return 0

    print(f"🎵 CLI Music is running at {url}  (Ctrl+C to quit)")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print()
    server.shutdown()
    return 0
