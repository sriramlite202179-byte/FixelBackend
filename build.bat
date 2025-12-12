@echo off
echo Running Fixel Backend Build...
python build/build.py
if %errorlevel% neq 0 (
    echo Build failed!
    exit /b %errorlevel%
)
echo Build success.
pause
