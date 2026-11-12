' Internal plugin detached runner: start the in-app session test without a console.
' wscript detaches the child, so it survives the launching tool call.
Set shell = CreateObject("WScript.Shell")
shell.Environment("Process")("VOICE_TYPER_INTERNAL_PLUGINS") = "1"
shell.CurrentDirectory = "C:\Users\11\voice-typer"
shell.Run """C:\Users\11\voice-typer\.venv\Scripts\python.exe"" tools/internal_plugins/google_stt/app_test.py", 0, False
