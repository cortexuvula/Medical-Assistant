# Creating Desktop Shortcuts for Medical Assistant

## Windows

### Option 1: Automatic Shortcut Creation
1. Double-click `create_desktop_shortcut.bat`
2. A desktop shortcut will be created with the custom icon

### Option 2: Manual Creation
1. Right-click on your desktop
2. Select "New" > "Shortcut"
3. Browse to `MedicalAssistant.exe` (in dist folder) or `MedicalAssistant.vbs`
4. Name it "Medical Assistant"
5. Right-click the shortcut > Properties
6. Click "Change Icon" and browse to `icon.ico`

## Linux

### Automatic Installation
```bash
./install_desktop_entry.sh
```

This will:
- Create a desktop entry in your applications menu
- Use the custom icon
- Make Medical Assistant searchable in your app launcher

### Manual Installation
1. Copy `medical-assistant.desktop` to `~/.local/share/applications/`
2. Edit the file to update the paths to match your installation
3. Run `update-desktop-database ~/.local/share/applications/`

## macOS

### From Finder
1. Navigate to the Medical Assistant app
2. Right-click and select "Make Alias"
3. Drag the alias to your desktop or dock

### From Terminal
```bash
ln -s /path/to/MedicalAssistant.app ~/Desktop/Medical\ Assistant
```

## Start Menu / Applications Menu

The application will automatically appear in:
- Windows: Start Menu (after running the installer)
- Linux: Applications menu (after running install_desktop_entry.sh)
- macOS: Applications folder (if copied there)

All shortcuts will display the custom Medical Assistant icon.