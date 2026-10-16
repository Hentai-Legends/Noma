@echo off
title Gemini Novel Translator
cd /d "%~dp0"

if "%~1"=="" (
    echo Memulai Gemini Novel Translator...
    python main.py
) else (
    echo Memproses file Drag and Drop: %~nx1
    python main.py "%~1"
)

if errorlevel 1 (
    echo [ERROR] Program terhenti dengan error.
)
pause
