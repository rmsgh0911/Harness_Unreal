"""Write a thin tracked HTML viewer for Harness/Progress.md."""

from __future__ import annotations

import argparse
import functools
import sys
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True

from harness_common import dump_json, find_project_root, harness_dir, rel, write_text


PROGRESS_RELATIVE = Path("Harness") / "Progress.md"
OUTPUT_RELATIVE = Path("Harness") / "Progress_index.html"
VIEWER_FILENAME = OUTPUT_RELATIVE.name


def render_html(source_path: str, generated_at: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="harness-progress-viewer" content="dynamic-source">
  <meta name="harness-progress-source" content="{source_path}">
  <title>Harness Progress</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #657080;
      --line: #d8dde5;
      --accent: #1f6feb;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 36px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0; font-size: 28px; font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 13px; text-align: right; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 18px;
    }}
    button, .file-button {{
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      border-radius: 6px;
      padding: 8px 12px;
      font: inherit;
      cursor: pointer;
    }}
    button:hover, .file-button:hover {{ border-color: var(--accent); }}
    input[type="file"] {{ display: none; }}
    .notice {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 16px;
      color: var(--muted);
      font-size: 14px;
    }}
    .notice.error {{ color: var(--danger); }}
    .hint {{
      display: none;
      border: 1px solid var(--accent);
      background: #eef4ff;
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 16px;
      font-size: 14px;
    }}
    .hint.show {{ display: block; }}
    .hint h2 {{ margin: 0 0 8px; font-size: 15px; }}
    .hint p {{ margin: 0 0 10px; }}
    .cmd-row {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }}
    .cmd-row code {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 10px;
      color: var(--text);
    }}
    .intro {{ color: var(--muted); margin: 0 0 18px; max-width: 820px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      min-height: 150px;
    }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li + li {{ margin-top: 8px; }}
    code {{ color: var(--accent); font-family: Consolas, "Courier New", monospace; }}
    @media (max-width: 720px) {{
      header {{ display: block; }}
      .meta {{ text-align: left; margin-top: 8px; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Harness Progress</h1></div>
      <div class="meta">
        <div>Viewer generated: {generated_at}</div>
        <div>Live source: <code id="source-label">{source_path}</code></div>
      </div>
    </header>
    <div class="toolbar">
      <button type="button" id="reload">Reload</button>
      <label class="file-button" for="file">Open Progress.md</label>
      <input id="file" type="file" accept=".md,text/markdown,text/plain">
    </div>
    <div id="notice" class="notice">Loading <code>{source_path}</code>...</div>
    <section id="file-hint" class="hint">
      <h2>Live view needs a local server</h2>
      <p>Browsers block reading <code>{source_path}</code> when this page is opened directly from disk (<code>file://</code>). Start a small local server to see the live dashboard:</p>
      <div class="cmd-row">
        <span>Double-click <code>Progress_view.cmd</code> (next to this file), or run:</span>
      </div>
      <div class="cmd-row">
        <code id="serve-cmd">python Harness/scripts/tools/harness_progress_html.py --serve</code>
        <button type="button" id="copy-cmd">Copy</button>
      </div>
      <p>Or click <strong>Open Progress.md</strong> above to load it once from disk.</p>
    </section>
    <p id="intro" class="intro"></p>
    <div id="grid" class="grid"></div>
  </main>
  <script>
    const SOURCE = "Progress.md";
    const notice = document.getElementById("notice");
    const intro = document.getElementById("intro");
    const grid = document.getElementById("grid");
    const reload = document.getElementById("reload");
    const file = document.getElementById("file");
    const fileHint = document.getElementById("file-hint");
    const copyCmd = document.getElementById("copy-cmd");
    const serveCmd = document.getElementById("serve-cmd");

    function setNotice(message, isError = false) {{
      notice.textContent = message;
      notice.classList.toggle("error", isError);
    }}

    function parseProgress(markdown) {{
      const parsed = {{ intro: [], sections: [] }};
      let current = null;
      for (const line of markdown.split(/\\r?\\n/)) {{
        if (line.startsWith("## ")) {{
          current = {{ title: line.slice(3).trim(), items: [], body: [] }};
          parsed.sections.push(current);
          continue;
        }}
        const trimmed = line.trim();
        if (!trimmed || line.startsWith("# ")) continue;
        if (!current) {{
          parsed.intro.push(trimmed);
        }} else if (trimmed.startsWith("- ")) {{
          current.items.push(trimmed.slice(2).trim());
        }} else {{
          current.body.push(trimmed);
        }}
      }}
      return parsed;
    }}

    function render(markdown, label) {{
      const parsed = parseProgress(markdown);
      intro.textContent = parsed.intro.join(" ");
      grid.replaceChildren();
      for (const section of parsed.sections) {{
        const card = document.createElement("section");
        card.className = "card";
        const title = document.createElement("h2");
        title.textContent = section.title;
        const list = document.createElement("ul");
        const items = section.items.length ? section.items : section.body.length ? section.body : ["No items."];
        for (const item of items) {{
          const li = document.createElement("li");
          li.textContent = item;
          list.append(li);
        }}
        card.append(title, list);
        grid.append(card);
      }}
      setNotice(`Loaded ${{label}} at ${{new Date().toLocaleString()}}.`);
      fileHint.classList.remove("show");
    }}

    async function loadSource() {{
      try {{
        const response = await fetch(SOURCE, {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        render(await response.text(), SOURCE);
      }} catch (error) {{
        fileHint.classList.add("show");
        setNotice(
          "Could not auto-load Progress.md over file://. Start the local server shown below for the live view, or click Open Progress.md.",
          true
        );
      }}
    }}

    reload.addEventListener("click", loadSource);
    file.addEventListener("change", async () => {{
      if (!file.files || !file.files[0]) return;
      render(await file.files[0].text(), file.files[0].name);
    }});
    copyCmd.addEventListener("click", async () => {{
      const text = serveCmd.textContent;
      try {{
        await navigator.clipboard.writeText(text);
        copyCmd.textContent = "Copied";
      }} catch (error) {{
        const range = document.createRange();
        range.selectNodeContents(serveCmd);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        try {{
          document.execCommand("copy");
          copyCmd.textContent = "Copied";
        }} catch (fallbackError) {{
          copyCmd.textContent = "Select the text and copy";
        }}
      }}
      setTimeout(() => {{ copyCmd.textContent = "Copy"; }}, 1500);
    }});

    if (location.protocol === "file:") {{
      fileHint.classList.add("show");
    }}

    loadSource();
  </script>
</body>
</html>
"""


def build_report(root: Path, write: bool = False) -> dict:
    source = root / PROGRESS_RELATIVE
    output = root / OUTPUT_RELATIVE
    generated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    html_text = render_html(PROGRESS_RELATIVE.as_posix(), generated_at)
    if write:
        write_text(output, html_text)
    return {
        "ok": source.exists(),
        "source": rel(source, root),
        "output": rel(output, root),
        "write": write,
        "output_exists": output.exists(),
        "viewer_mode": "dynamic-source",
        "html": html_text if not write else "",
    }


def build_server(root: Path, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Create a localhost static server rooted at the Harness directory.

    Returns the running server and the URL of the Progress viewer. The caller
    owns the lifecycle: call ``serve_forever`` then ``server_close``. Binding to
    ``127.0.0.1`` keeps the convenience viewer off the network, and port ``0``
    lets the OS pick a free port.
    """
    serve_root = harness_dir(root)
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(serve_root))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    bound_port = httpd.server_address[1]
    return httpd, f"http://127.0.0.1:{bound_port}/{VIEWER_FILENAME}"


def serve(root: Path, port: int = 0, open_browser: bool = True) -> int:
    """Serve Harness/ on localhost so the viewer can fetch the live Progress.md."""
    viewer = root / OUTPUT_RELATIVE
    if not viewer.exists():
        print(f"Viewer missing: {rel(viewer, root)}. Run with --write first to generate it.")
    httpd, url = build_server(root, port=port)
    print(f"Serving live Harness Progress viewer at {url}")
    print("Live source: Harness/Progress.md (served over HTTP so fetch works).")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            print("Could not open a browser automatically; open the URL above manually.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


def format_text(report: dict) -> str:
    lines = [
        "Harness Progress HTML",
        f"- Source: {report['source']}",
        f"- Output: {report['output']}",
        f"- Write: {report['write']}",
        f"- Output exists: {report['output_exists']}",
        f"- Viewer mode: {report['viewer_mode']}",
    ]
    if report.get("html"):
        lines.extend(["", report["html"]])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a thin Harness/Progress_index.html viewer for Harness/Progress.md.")
    parser.add_argument("--root", type=Path, default=None, help="Project root. Defaults to nearest Harness root.")
    parser.add_argument("--write", action="store_true", help="Write Harness/Progress_index.html.")
    parser.add_argument("--serve", action="store_true", help="Serve Harness/ on localhost and open the live viewer so fetch works.")
    parser.add_argument("--port", type=int, default=0, help="Port for --serve. Default 0 auto-selects a free port.")
    parser.add_argument("--no-browser", action="store_true", help="With --serve, do not auto-open a browser.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    root = find_project_root(args.root)
    if args.serve:
        raise SystemExit(serve(root, port=args.port, open_browser=not args.no_browser))
    report = build_report(root, write=args.write)
    if args.json:
        data = dict(report)
        if data.get("html"):
            data["html"] = ""
        print(dump_json(data))
    else:
        print(format_text(report))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
