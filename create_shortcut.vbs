' Create Desktop Shortcut for Medical Assistant with Custom Icon
' Run this script to create a desktop shortcut with the custom icon

Set WshShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get paths
strDesktop = WshShell.SpecialFolders("Desktop")
strCurrentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Create shortcut on desktop
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\Medical Assistant.lnk")

' Check if compiled version exists
strExePath = strCurrentDir & "\dist\MedicalAssistant.exe"
If objFSO.FileExists(strExePath) Then
    ' Point to compiled executable
    oShellLink.TargetPath = strExePath
    oShellLink.WorkingDirectory = strCurrentDir & "\dist"
Else
    ' Point to the VBS launcher for development
    oShellLink.TargetPath = strCurrentDir & "\MedicalAssistant.vbs"
    oShellLink.WorkingDirectory = strCurrentDir
End If

' Set the icon
strIconPath = strCurrentDir & "\icon.ico"
If objFSO.FileExists(strIconPath) Then
    oShellLink.IconLocation = strIconPath & ",0"
Else
    ' Try alternate icon
    strIconPath = strCurrentDir & "\icon256x256.ico"
    If objFSO.FileExists(strIconPath) Then
        oShellLink.IconLocation = strIconPath & ",0"
    End If
End If

' Set other properties
oShellLink.Description = "Medical Assistant - Voice-powered medical documentation"
oShellLink.WindowStyle = 1

' Save the shortcut
oShellLink.Save

MsgBox "Desktop shortcut created successfully!" & vbCrLf & vbCrLf & _
       "The shortcut will use the custom icon.", 64, "Medical Assistant"