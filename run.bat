@echo off
echo Starting AI Exam Analyzer...

if not exist ".env" (
    echo WARNING: .env file not found. AI features might not work without GEMINI_API_KEY.
    echo Please copy .env.example to .env and add your API key.
    echo.
)

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    python app.py
) else (
    echo Error: venv not found. Please create a virtual environment first.
    pause
)
