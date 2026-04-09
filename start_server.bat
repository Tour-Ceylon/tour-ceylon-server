@echo off
echo Starting Tour Ceylon Backend Server...
echo.

cd /d "%~dp0"
echo Current directory: %cd%
echo.

echo Checking Python version...
python --version
echo.

echo Loading environment variables...
if exist .env (
    echo .env file found, loading variables...
    for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
) else (
    echo Warning: .env file not found
)

echo.
echo Setting PYTHONPATH...
set PYTHONPATH=%cd%

echo.
echo Starting FastAPI server with uvicorn on port 8000...
python start_server.py

pause