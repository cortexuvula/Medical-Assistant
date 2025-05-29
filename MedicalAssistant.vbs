' Medical Assistant Launcher with Icon
' This VBScript creates a shortcut with the custom icon

Set WshShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the current directory
strCurrentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Check if running compiled version or development version
strExePath = strCurrentDir & "\dist\MedicalAssistant.exe"
strIconPath = strCurrentDir & "\icon.ico"

If objFSO.FileExists(strExePath) Then
    ' Run the compiled executable
    WshShell.Run Chr(34) & strExePath & Chr(34), 1, False
Else
    ' Run the Python script in development mode
    strBatPath = strCurrentDir & "\launch_app.bat"
    If objFSO.FileExists(strBatPath) Then
        WshShell.Run Chr(34) & strBatPath & Chr(34), 1, False
    Else
        MsgBox "Could not find MedicalAssistant.exe or launch_app.bat", 16, "Medical Assistant"
    End If
End If