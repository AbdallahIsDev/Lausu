' Internal plugin hotkey + Google STT daemon launcher (hidden window). NEVER SHIP.
' Sits in the user's Startup folder; runs the internal plugin in the project venv.
Set shell = CreateObject("WScript.Shell")
shell.Environment("Process")("VOICE_TYPER_INTERNAL_PLUGINS") = "1"
shell.CurrentDirectory = "C:\Users\11\voice-typer\tools\internal_plugins\google_stt"
' 1) daemon (Playwright control plane), 2) hotkey listener
shell.Run """C:\Program Files\nodejs\node.exe"" run.js", 0, False
WScript.Sleep 3000
shell.Run """C:\Users\11\voice-typer\.venv\Scripts\pythonw.exe"" hotkey.py", 0, False
