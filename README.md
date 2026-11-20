# MCQ Helper

Background tool for Windows. It takes a screenshot when you press a hotkey, sends it to a local Ollama vision model (`MichelRosselli/bonsai-27b`), and shows the answer in a small popup. Each answer is the option letter plus a 2-line explanation. The prompt is tuned for computer architecture and Irvine x86 MASM assembly.

## Setup

```powershell
pip install -r requirements.txt
```

If the model isn't installed, it downloads automatically (about 4.4 GB) the first time the program starts. If you press `Ctrl+Shift+X` while it is still downloading, the popup shows the download progress. You can also download it yourself first with `ollama pull MichelRosselli/bonsai-27b`.

## Run

Double-click `start.bat`, or run `pythonw mcq_helper.py`. Nothing appears on screen. The program waits in the background and loads the model at startup.

| Hotkey | Action |
| --- | --- |
| `Ctrl+Shift+X` | Take a screenshot and show the answer popup (top-right corner) |
| `Ctrl+Shift+Z` | Hide the popup. The program keeps running |
| `Ctrl+Shift+Q` | Quit |

A small notification in the bottom-right corner tells you what the program is doing:

- On start: "MCQ Helper is running in the background", with the hotkey list
- While the model loads or downloads: loading message or download progress, then "Model ready"
- After `Ctrl+Shift+X`: "Screenshot taken · Thinking… 5s", with a live timer until the answer appears
- On `Ctrl+Shift+Q`: "MCQ Helper stopped"

Logs and errors are written to `mcq_helper.log`.

## Config

Settings are at the top of `mcq_helper.py`: `MODEL`, hotkeys, `MAX_IMAGE_SIDE`, `POPUP_WIDTH` and the system prompt.

To start it automatically with Windows, press `Win+R`, type `shell:startup`, and put a shortcut to `start.bat` in that folder.
