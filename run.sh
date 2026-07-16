#!/usr/bin/env bash
# ==============================================================================
# FocusGuardian Startup Script.
# Coordinates virtual environment setup, C++ compilation, and main execution.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🧘 Guardian of health - AI Health Assistant"
echo "==========================================="

# 1. Verify Python version (3.12 is highly recommended)
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$python_version" != "3.12" ]]; then
    echo "⚠️  Warning: Python 3.12 is recommended (detected: $python_version)"
fi

# 2. Check for C++ compilation requirements (compiler and build tools)
if ! command -v g++ &> /dev/null; then
    echo "❌ Error: g++ compiler is not installed. Please install build-essential."
    exit 1
fi

# 3. Create and set up virtual environment if it doesn't exist.
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    
    # Activate virtual environment.
    source venv/bin/activate
    
    echo "⚙️  Upgrading pip, setuptools, and wheel..."
    pip install --upgrade pip setuptools wheel
    
    if [ -f "requirements.txt" ]; then
        echo "📥 Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        echo "⚠️  Warning: requirements.txt not found!"
    fi
else
    # Reuse existing virtual environment.
    source venv/bin/activate
fi

# 4. Compile the C++ video engine extension.
echo "🔧 Building C++ extension (video_engine)..."
python setup.py build_ext --inplace

# 5. Execute the main application with passed arguments.
echo "🚀 Starting Guardian of health..."
python main.py "$@"
