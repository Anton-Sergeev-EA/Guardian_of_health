@echo off
REM ==============================================================================
REM Guardian of health Windows Startup Script
REM Coordinates virtual environment setup, C++ compilation, and main execution.
REM ==============================================================================

setlocal enabledelayedexpansion

echo 🧘 Guardian of health - AI Health Assistant
echo ===========================================

REM 1. Verify if Python is installed and accessible
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not added to PATH.
    echo Please install Python 3.12 and check "Add Python to PATH" during setup.
    pause
    exit /b 1
)

REM 2. Check Python version (warn if it is not 3.12)
for /f "tokens=2" %%I in ('python -V 2^>^&1') do set "PY_VER=%%I"
echo %PY_VER% | findstr /r "^3\.12" >nul
if errorlevel 1 (
    echo ⚠️  Warning: Python 3.12 is highly recommended (detected: %PY_VER%^)
)

REM 3. Create and set up virtual environment if it does not exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
    
    REM Activate newly created virtual environment
    call venv\Scripts\activate.bat
    
    echo ⚙️  Upgrading pip, setuptools, and wheel...
    python -m pip install --upgrade pip setuptools wheel
    
    if exist "requirements.txt" (
        echo 📥 Installing dependencies from requirements.txt...
        pip install -r requirements.txt
    ) else (
        echo ⚠️  Warning: requirements.txt not found!
    )
) else (
    REM Activate existing virtual environment
    call venv\Scripts\activate.bat
)

REM 4. Compile the C++ video engine extension
echo 🔧 Building C++ extension (video_engine)...
echo Note: This step requires MSVC compiler (Visual Studio Build Tools with C++ workload).
python setup.py build_ext --inplace
if errorlevel 1 (
    echo ⚠️  Warning: C++ extension build failed. 
    echo Please ensure you have Desktop development with C++ installed via Visual Studio Installer.
)

REM 5. Execute the main application with passed arguments
echo 🚀 Starting Guardian of health...
python main.py %*

pause
