"""
Download FFmpeg binaries for bundling with PyInstaller
"""
import os
import sys
import platform
import urllib.request
import zipfile
import tarfile
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# FFmpeg download URLs
FFMPEG_URLS = {
    'windows': {
        'url': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
        'extract_path': 'ffmpeg-master-latest-win64-gpl/bin',
        'files': ['ffmpeg.exe', 'ffprobe.exe']
    },
    'darwin': {  # macOS
        'url': 'https://evermeet.cx/pub/ffmpeg/ffmpeg-7.0.zip',
        'extract_path': '',
        'files': ['ffmpeg']
    },
    'linux': {
        'url': 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz',
        'extract_path': 'ffmpeg-master-latest-linux64-gpl/bin',
        'files': ['ffmpeg', 'ffprobe']
    }
}

def download_file(url, destination):
    """Download a file from URL to destination with progress"""
    logging.info(f"Downloading from {url}")
    
    def download_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, (downloaded / total_size) * 100) if total_size > 0 else 0
        if block_num % 100 == 0:  # Log every 100 blocks
            logging.info(f"Download progress: {percent:.1f}%")
    
    try:
        urllib.request.urlretrieve(url, destination, reporthook=download_progress)
        logging.info(f"Downloaded to {destination}")
    except Exception as e:
        logging.error(f"Download failed: {e}")
        raise

def extract_archive(archive_path, extract_to):
    """Extract archive based on file extension"""
    logging.info(f"Extracting {archive_path}")
    
    if archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.endswith(('.tar.xz', '.tar.gz')):
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            tar_ref.extractall(extract_to)
    else:
        raise ValueError(f"Unsupported archive format: {archive_path}")
    
    logging.info(f"Extracted to {extract_to}")

def download_ffmpeg():
    """Download FFmpeg for the current platform"""
    system = platform.system().lower()
    
    if system not in FFMPEG_URLS:
        logging.error(f"Unsupported platform: {system}")
        return False
    
    config = FFMPEG_URLS[system]
    
    # Create ffmpeg directory
    ffmpeg_dir = os.path.join(os.path.dirname(__file__), 'ffmpeg')
    os.makedirs(ffmpeg_dir, exist_ok=True)
    
    # Download archive
    archive_name = os.path.basename(config['url'])
    archive_path = os.path.join(ffmpeg_dir, archive_name)
    
    try:
        download_file(config['url'], archive_path)
        
        # Extract archive
        temp_extract_dir = os.path.join(ffmpeg_dir, 'temp_extract')
        os.makedirs(temp_extract_dir, exist_ok=True)
        extract_archive(archive_path, temp_extract_dir)
        
        # Copy required files
        extract_path = os.path.join(temp_extract_dir, config['extract_path'])
        for file_name in config['files']:
            src_path = os.path.join(extract_path, file_name)
            dst_path = os.path.join(ffmpeg_dir, file_name)
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                # Make executable on Unix
                if system != 'windows':
                    os.chmod(dst_path, 0o755)
                logging.info(f"Copied {file_name} to {dst_path}")
            else:
                logging.warning(f"File not found: {src_path}")
        
        # Clean up
        os.remove(archive_path)
        shutil.rmtree(temp_extract_dir)
        
        logging.info("FFmpeg download complete!")
        return True
        
    except Exception as e:
        logging.error(f"Error downloading FFmpeg: {e}")
        return False

if __name__ == "__main__":
    success = download_ffmpeg()
    sys.exit(0 if success else 1)