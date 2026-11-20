"""
MCQ Helper - background screenshot -> Ollama vision model -> answer popup.

Hotkeys
  Ctrl+Shift+X : take a screenshot, send it to the model, show the answer popup
  Ctrl+Shift+Z : hide the popup (program keeps running in the background)
  Ctrl+Shift+Q : quit the program

Run with  pythonw mcq_helper.py  (or start.bat) so no console window appears.
Logs go to mcq_helper.log next to this file.
"""

import base64
import ctypes
import io
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request

import keyboard
from PIL import ImageGrab

# ----------------------------------------------------------------- settings
MODEL = "MichelRosselli/bonsai-27b"
OLLAMA_URL = "http://127.0.0.1:11434"
HOTKEY_CAPTURE = "ctrl+shift+x"
HOTKEY_HIDE = "ctrl+shift+z"
HOTKEY_QUIT = "ctrl+shift+q"
MAX_IMAGE_SIDE = 1920        # downscale big screenshots to save tokens/time
REQUEST_TIMEOUT = 600        # seconds to wait for the model
POPUP_WIDTH = 460

SYSTEM_PROMPT = (
    "You are an expert in computer organization & architecture and x86 assembly "
    "language (Kip Irvine, MASM, 32-bit/64-bit Intel registers, flags, addressing "
    "modes, instructions like MOV/ADD/SUB/INC/DEC/LOOP/JMP/Jcc/CMP/TEST/PUSH/POP/"
    "CALL/RET/MUL/IMUL/DIV/IDIV/SHL/SHR/SAR/ROL/ROR, directives like PROC/ENDP/"
    "DWORD/BYTE/OFFSET/PTR/TYPE/LENGTHOF/SIZEOF, memory, pipelining, caches, etc.).\n"
    "The image is a screenshot containing one or more multiple-choice questions. "
    "For EVERY question visible in the image, reply in exactly this format and "
    "nothing else:\n\n"
    "Q<number>: <option letter>) <option text, short>\n"
    "<explanation in at most 2 short lines>\n\n"
    "Trace any register/flag values carefully before answering. "
    "Do not repeat the question. Do not add an introduction or conclusion."
)
USER_PROMPT = "Answer the MCQs in this screenshot."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "mcq_helper.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("mcq")

# Make screenshots use real pixels on scaled (125%/150%) displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ------------------------------------------------------------------ ollama
def _http(path, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ollama_running():
    try:
        _http("/api/version", timeout=3)
        return True
    except Exception:
        return False


def ensure_ollama_server():
    """Start `ollama serve` hidden if no server is reachable."""
    if ollama_running():
        return True
    exe = shutil.which("ollama")
    if not exe:
        log.error("ollama executable not found on PATH")
        return False
    log.info("starting ollama serve")
    subprocess.Popen(
        [exe, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(60):
        time.sleep(1)
        if ollama_running():
            return True
    log.error("ollama server did not come up")
    return False


def model_installed():
    try:
        names = [m.get("name", "") for m in _http("/api/tags").get("models", [])]
    except Exception:
        return False
    return any(n == MODEL or n.split(":")[0] == MODEL for n in names)


def pull_model(on_progress=None):
    """Download the model via Ollama's /api/pull, reporting progress text."""
    log.info("model %s not installed, downloading", MODEL)
    req = urllib.request.Request(
        OLLAMA_URL + "/api/pull",
        data=json.dumps({"model": MODEL, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_logged = -10
    with urllib.request.urlopen(req, timeout=300) as resp:
        for line in resp:
            if not line.strip():
                continue
            msg = json.loads(line.decode())
            if "error" in msg:
                raise RuntimeError(f"Model download failed: {msg['error']}")
            status = msg.get("status", "")
            total, done = msg.get("total"), msg.get("completed")
            if total and done is not None:
                pct = int(done * 100 / total)
                text = f"{status} {pct}% ({done / 1e9:.2f}/{total / 1e9:.2f} GB)"
                if pct >= last_logged + 10:
                    log.info("pull: %s", text)
                    last_logged = pct
            else:
                text = status
                log.info("pull: %s", status)
            if on_progress:
                on_progress(text)
    if not model_installed():
        raise RuntimeError("Model download finished but the model is not listed.")
    log.info("model %s downloaded", MODEL)


def preload_model():
    """Load the model into memory and keep it there so answers come faster."""
    try:
        _http(
            "/api/generate",
            {"model": MODEL, "prompt": "", "keep_alive": -1},
            timeout=REQUEST_TIMEOUT,
        )
        log.info("model %s loaded", MODEL)
    except Exception as e:
        log.error("preload failed: %s", e)


def ask_model(png_b64):
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,          # bonsai is a thinking model; skip it for speed
        "keep_alive": -1,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT, "images": [png_b64]},
        ],
    }
    try:
        resp = _http("/api/chat", payload, timeout=REQUEST_TIMEOUT)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        if "think" in body.lower():          # older/other models reject `think`
            payload.pop("think")
            resp = _http("/api/chat", payload, timeout=REQUEST_TIMEOUT)
        else:
            raise RuntimeError(f"HTTP {e.code}: {body}") from e
    text = resp.get("message", {}).get("content", "")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # just in case
    return text.strip() or "(model returned an empty answer)"


# -------------------------------------------------------------- screenshot
def take_screenshot_b64():
    img = ImageGrab.grab()  # primary monitor
    w, h = img.size
    scale = MAX_IMAGE_SIDE / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------- popup
class Popup:
    """Borderless always-on-top answer card. Lives on the Tk main thread."""

    BG = "#111418"
    FG = "#e8eaed"
    ACCENT = "#4fc3f7"

    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.94)
        self.win.configure(bg=self.ACCENT)  # 1px accent border

        inner = tk.Frame(self.win, bg=self.BG, padx=14, pady=10)
        inner.pack(padx=1, pady=1, fill="both", expand=True)
        self.title = tk.Label(
            inner, bg=self.BG, fg=self.ACCENT, anchor="w",
            font=("Segoe UI Semibold", 10),
        )
        self.title.pack(fill="x")
        self.body = tk.Label(
            inner, bg=self.BG, fg=self.FG, justify="left", anchor="w",
            font=("Segoe UI", 10), wraplength=POPUP_WIDTH - 30,
        )
        self.body.pack(fill="both", expand=True, pady=(6, 0))
        self.hint = tk.Label(
            inner, bg=self.BG, fg="#80868b", anchor="e",
            font=("Segoe UI", 8), text="Ctrl+Shift+Z to hide",
        )
        self.hint.pack(fill="x", pady=(6, 0))

    def show(self, title, text):
        self.title.config(text=title)
        self.body.config(text=text)
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        h = min(self.win.winfo_reqheight(), self.win.winfo_screenheight() - 80)
        self.win.geometry(f"{POPUP_WIDTH}x{h}+{sw - POPUP_WIDTH - 20}+20")
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)

    def hide(self):
        self.win.withdraw()

    @property
    def visible(self):
        return self.win.state() != "withdrawn"


# -------------------------------------------------------------------- app
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.popup = Popup(self.root)
        self.events = queue.Queue()
        self.busy = threading.Lock()
        self.init_lock = threading.Lock()
        self.ready = False
        self.pull_status = None  # text while the model is downloading

    # called from the keyboard hook thread -> just enqueue
    def on_capture(self):
        self.events.put(("capture", None))

    def on_hide(self):
        self.events.put(("hide", None))

    def on_quit(self):
        self.events.put(("quit", None))

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "capture":
                    self.start_capture()
                elif kind == "hide":
                    self.popup.hide()
                elif kind == "answer":
                    self.popup.show("Answer", data)
                elif kind == "error":
                    self.popup.show("Error", data)
                elif kind == "quit":
                    self.shutdown()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def start_capture(self):
        if not self.busy.acquire(blocking=False):
            log.info("busy, ignoring hotkey")
            return
        # Hide our own popup so it is not in the screenshot.
        was_visible = self.popup.visible
        self.popup.hide()
        self.root.update()
        delay = 150 if was_visible else 0
        self.root.after(delay, self._grab_and_ask)

    def _grab_and_ask(self):
        try:
            img_b64 = take_screenshot_b64()
        except Exception as e:
            log.exception("screenshot failed")
            self.busy.release()
            self.events.put(("error", f"Screenshot failed: {e}"))
            return
        threading.Thread(target=self._worker, args=(img_b64,), daemon=True).start()

    def _worker(self, img_b64):
        try:
            if self.pull_status is not None:
                self.events.put((
                    "error",
                    f"Model is still downloading:\n{self.pull_status}\n\n"
                    "Press Ctrl+Shift+X again when it finishes.",
                ))
                return
            if not self.ready:
                self.startup_checks()
            t0 = time.time()
            answer = ask_model(img_b64)
            log.info("answer in %.1fs:\n%s", time.time() - t0, answer)
            self.events.put(("answer", answer))
        except Exception as e:
            log.exception("model request failed")
            self.events.put(("error", str(e)))
        finally:
            self.busy.release()

    def startup_checks(self):
        with self.init_lock:  # only one thread starts the server / downloads
            if self.ready:
                return
            if not ensure_ollama_server():
                raise RuntimeError(
                    "Ollama server is not running and could not be started.")
            if not model_installed():
                self.pull_status = "starting download..."
                try:
                    pull_model(self._set_pull_status)
                finally:
                    self.pull_status = None
            self.ready = True

    def _set_pull_status(self, text):
        self.pull_status = text

    def background_init(self):
        try:
            self.startup_checks()
            preload_model()
        except Exception as e:
            log.error("startup: %s", e)

    def shutdown(self):
        log.info("quitting")
        keyboard.unhook_all()
        self.root.destroy()

    def run(self):
        keyboard.add_hotkey(HOTKEY_CAPTURE, self.on_capture, suppress=False)
        keyboard.add_hotkey(HOTKEY_HIDE, self.on_hide, suppress=False)
        keyboard.add_hotkey(HOTKEY_QUIT, self.on_quit, suppress=False)
        threading.Thread(target=self.background_init, daemon=True).start()
        log.info("running; %s capture, %s hide, %s quit",
                 HOTKEY_CAPTURE, HOTKEY_HIDE, HOTKEY_QUIT)
        self.root.after(50, self.poll)
        self.root.mainloop()


def single_instance():
    """Prevent two copies from running (both would answer the hotkey)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\MCQHelperMutex")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if not single_instance():
        sys.exit(0)
    App().run()
