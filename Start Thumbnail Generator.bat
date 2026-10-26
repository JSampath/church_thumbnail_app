@echo off
rem Double-click to start the Livestream Thumbnail Generator.
rem The first run sets everything up (about a minute, needs internet).
title Livestream Thumbnail Generator
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo First run: getting things ready, this takes about a minute...
  where py >nul 2>nul
  if not errorlevel 1 (py -3 -m venv venv) else (python -m venv venv)
  if not exist "venv\Scripts\python.exe" goto nopython
  "venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)

rem Skip Streamlit's one-time "Email:" question so the app opens straight away.
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
  > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
  >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo Opening the app in your browser. Keep this window open while you use it.
"venv\Scripts\python.exe" -m streamlit run app.py
goto :eof

:nopython
echo.
echo Python is not installed on this computer.
echo Install Python 3 from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH"), then double-click this file again.
pause
goto :eof

:failed
echo.
echo Setting up failed. Check the internet connection and double-click this file again.
pause
