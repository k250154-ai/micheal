# MCQ Helper

Background tool for Windows. It takes a screenshot when you press a hotkey, sends it to a local Ollama vision model (`MichelRosselli/bonsai-27b`), and shows the answer in a small popup. Each answer is the option letter plus a 2-line explanation. The prompt is tuned for computer architecture and Irvine x86 MASM assembly.

## Setup

```powershell
pip install -r requirements.txt
ollama pull MichelRosselli/bonsai-27b
```

## Run

Double-click `start.bat`, or run `pythonw mcq_helper.py`. Nothing appears on screen. The program waits in the background and loads the model at startup.

| Hotkey | Action |
| --- | --- |
| `Ctrl+Shift+X` | Take a screenshot and show the answer popup (top-right corner) |
| `Ctrl+Shift+Z` | Hide the popup. The program keeps running |
| `Ctrl+Shift+Q` | Quit |

Logs and errors are written to `mcq_helper.log`.

## Config

Settings are at the top of `mcq_helper.py`: `MODEL`, hotkeys, `MAX_IMAGE_SIDE`, `POPUP_WIDTH` and the system prompt.

To start it automatically with Windows, press `Win+R`, type `shell:startup`, and put a shortcut to `start.bat` in that folder.
