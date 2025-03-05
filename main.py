import sys

# Check Python version before importing app
if sys.version_info < (3, 10):
    print("Error: This application requires Python 3.10 or higher.")
    print(f"Your current Python version is {sys.version}")
    print("\nPlease update your Python version or create a new environment with Python 3.10+.")
    print("\nSuggested fix: Use conda to create a new environment with Python 3.10:")
    print("conda create -n medical_dictation python=3.10")
    print("conda activate medical_dictation")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Import app only if Python version is compatible
from app import main

if __name__ == "__main__":
    main()
