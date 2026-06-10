@echo off
REM Quick Start Script for PapersNav (Windows)

echo.
echo 🚀 Starting PapersNav Setup...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

echo ✓ Python found
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo 📦 Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install requirements
echo 📥 Installing dependencies...
pip install -r requirements.txt -q

REM Check if .env exists
if not exist ".env" (
    echo.
    echo ⚠️  .env file not found
    echo 📝 Creating .env from .env.example...
    copy .env.example .env
    echo ✓ .env created - please edit it with your MongoDB URI and other settings
)

echo.
echo ✅ Setup complete!
echo.
echo 📋 Next steps:
echo    1. Edit .env with your MongoDB connection string
echo    2. Run: python app.py
echo    3. Open: http://localhost:5000
echo.
pause
