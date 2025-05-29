# Creating Icons for Medical Assistant

## Windows Icon (.ico)

### Option 1: Online Converter
1. Go to https://convertio.co/png-ico/ or https://www.icoconverter.com/
2. Upload your PNG image (preferably 256x256 or larger)
3. Download the .ico file
4. Rename it to `icon.ico` and place in project root

### Option 2: Using ImageMagick (command line)
```bash
# Install ImageMagick first, then:
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

### Option 3: Using GIMP
1. Open your image in GIMP
2. Scale to 256x256 if needed
3. Export as `.ico`
4. Select multiple sizes when prompted

## macOS Icon (.icns)

### Option 1: Using iconutil (macOS only)
```bash
# Create iconset directory
mkdir icon.iconset

# Create required sizes from your original image (icon_1024.png)
sips -z 16 16     icon_1024.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon_1024.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon_1024.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon_1024.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon_1024.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon_1024.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon_1024.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon_1024.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon_1024.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 icon_1024.png --out icon.iconset/icon_512x512@2x.png

# Convert to icns
iconutil -c icns icon.iconset
```

### Option 2: Online Converter
1. Go to https://cloudconvert.com/png-to-icns
2. Upload your PNG image
3. Download the .icns file
4. Rename it to `icon.icns` and place in project root

## Icon Design Tips
- Use a simple, recognizable design
- Ensure it looks good at small sizes (16x16)
- Use transparency for better integration
- Consider using medical-related imagery (stethoscope, cross, etc.)
- Test visibility on different backgrounds

## After Creating Icons
1. Place `icon.ico` (Windows) and/or `icon.icns` (macOS) in project root
2. Rebuild with PyInstaller: `python -m PyInstaller medical_assistant.spec --clean`
3. The executable will now use your custom icon