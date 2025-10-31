Set shell = CreateObject("WScript.Shell")

' Try to auto-detect Python in PATH first
On Error Resume Next
shell.Run "python ""Computer_Main_Centre.py""", 1, False
If Err.Number <> 0 Then
    ' If that fails, try py launcher (works on most systems)
    Err.Clear
    shell.Run "py ""Computer_Main_Centre.py""", 1, False
End If

If Err.Number <> 0 Then
    MsgBox "Python not found! Please install Python 3 and ensure it's added to PATH.", vbCritical, "CMC Startup Error"
End If

