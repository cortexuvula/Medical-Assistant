# ADR-001: Tkinter as UI Framework

## Status

Accepted

## Date

2024-01

## Context

Medical Assistant requires a desktop GUI for clinical documentation workflows. The application needs to:

- Run on Windows, macOS, and Linux
- Support real-time audio recording and playback
- Display multiple text editors simultaneously (transcript, SOAP note, referral, letter)
- Integrate with system audio devices
- Be distributable as a standalone executable without requiring users to install Python
- Start quickly and remain responsive during AI API calls

The target users are healthcare professionals who need a reliable, fast-launching desktop application for clinical documentation during patient encounters.

## Decision

We chose **Tkinter with ttkbootstrap** as the UI framework.

Tkinter is Python's standard GUI library, and ttkbootstrap provides modern Bootstrap-inspired themes and widgets on top of ttk (themed Tkinter).

## Consequences

### Positive

- **Zero dependencies for basic UI**: Tkinter ships with Python, simplifying distribution
- **Cross-platform**: Works on Windows, macOS, and Linux with consistent behavior
- **Fast startup**: Tkinter applications launch quickly (sub-second) compared to Electron or web-based alternatives
- **Low memory footprint**: ~50-100MB RAM vs 200-500MB for Electron apps
- **PyInstaller compatibility**: Excellent support for bundling into standalone executables
- **Native feel**: Uses native widgets where possible, feels appropriate on each OS
- **ttkbootstrap themes**: Modern appearance without the complexity of custom styling
- **Mature and stable**: Tkinter has been stable for decades, minimal breaking changes
- **Threading model**: Simple integration with Python threading for background tasks

### Negative

- **Limited modern UI patterns**: No built-in support for animations, transitions, or complex layouts
- **Callback-based**: Event handling is more verbose than reactive frameworks
- **Widget limitations**: Some advanced widgets (rich text, markdown rendering) require custom implementation
- **Scaling issues**: DPI scaling on Windows can be problematic (mitigated with manifest settings)
- **Learning curve for contributors**: Less common than web frameworks, fewer developers familiar with it
- **No hot reload**: Changes require application restart during development

### Neutral

- Custom widgets needed for specialized views (graph canvas, RSVP reader)
- ttkbootstrap adds ~2MB to distribution size

## Alternatives Considered

### Electron / Tauri

**Rejected because:**
- Electron: 150MB+ distribution size, 200-500MB RAM usage, slower startup
- Tauri: Rust backend would complicate the Python-centric codebase
- Both: Overkill for a desktop app that doesn't need web technologies
- Both: More complex audio device integration

### PyQt / PySide

**Rejected because:**
- Licensing complexity (GPL/LGPL/Commercial)
- Larger distribution size (~50MB for Qt libraries)
- Steeper learning curve
- More complex PyInstaller configuration

### Dear PyGui / Kivy

**Rejected because:**
- Less mature ecosystems
- Fewer resources and community support
- Custom rendering may have accessibility issues
- Less native feel on desktop platforms

### Web-based (Flask/FastAPI + Browser)

**Rejected because:**
- Requires browser to be open
- Complex audio device access from browser
- Not a true desktop application experience
- Deployment complexity for non-technical users

## References

- [Tkinter documentation](https://docs.python.org/3/library/tkinter.html)
- [ttkbootstrap documentation](https://ttkbootstrap.readthedocs.io/)
- [PyInstaller Tkinter support](https://pyinstaller.org/en/stable/)
