import asyncio
import base64
import json
import os
import subprocess
import tempfile
import urllib.request
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = r"C:\Users\Raza\Downloads\konnextBinMcp\snapshot"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "full_dashboard.png")
TARGET_URL = "http://localhost:8999"

async def capture_full_page():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    user_data_dir = tempfile.mkdtemp(prefix="chrome_cdp_")
    port = 9447

    args = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--window-size=1920,2600",
        "--hide-scrollbars",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        TARGET_URL,
    ]

    print("Launching Chrome on port 9447...", flush=True)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ws_url = None
        for attempt in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as resp:
                    tabs = json.loads(resp.read().decode())
                    if tabs:
                        ws_url = tabs[0].get("webSocketDebuggerUrl")
                        if ws_url:
                            break
            except Exception:
                await asyncio.sleep(0.25)

        if not ws_url:
            raise RuntimeError("Failed to connect to Chrome DevTools WebSocket")

        print(f"Connected to CDP WebSocket: {ws_url}", flush=True)
        async with websockets.connect(ws_url, max_size=50_000_000, ping_interval=None) as ws:
            msg_id = 0

            async def send_cmd(method, params=None):
                nonlocal msg_id
                msg_id += 1
                payload = {"id": msg_id, "method": method, "params": params or {}}
                print(f"Sending {method} (id={msg_id})...", flush=True)
                await ws.send(json.dumps(payload))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=25)
                    res = json.loads(raw)
                    if res.get("id") == msg_id:
                        if "error" in res:
                            print(f"CDP Error in {method}: {res['error']}", flush=True)
                        return res.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd("Runtime.enable")

            print("Waiting 5s for signals and charts to render...", flush=True)
            await asyncio.sleep(5)

            print("Capturing full page screenshot...", flush=True)
            res = await send_cmd("Page.captureScreenshot", {
                "format": "png",
                "fromSurface": True
            })

            data_str = res.get("data")
            if not data_str:
                raise RuntimeError(f"No screenshot data returned: {res}")

            img_data = base64.b64decode(data_str)
            with open(OUTPUT_FILE, "wb") as f:
                f.write(img_data)

            print(f"SUCCESS: Snapshot saved to {OUTPUT_FILE} ({len(img_data)} bytes)", flush=True)

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(capture_full_page())
