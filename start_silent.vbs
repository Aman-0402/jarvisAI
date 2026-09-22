' Launches Jarvis with no console window — used by the autostart registry entry.
Set objShell = CreateObject("WScript.Shell")
strPath = objShell.CurrentDirectory
objShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run """" & objShell.CurrentDirectory & "\.venv\Scripts\pythonw.exe"" -m jarvis.main", 0, False
