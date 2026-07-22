@echo off
REM ===========================================================================
REM run.bat - Run Accounting System on LAN + localhost
REM Keep this window open. Press Ctrl+C to stop.
REM ===========================================================================
cd /d "%~dp0"

set DJANGO_DEBUG=true
REM Port and hosts are read from network.conf

python run_multi.py
pause
