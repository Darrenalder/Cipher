@echo off
rem Dev-Start ohne Konsolenfenster (pythonw). Logs landen in logs\own-browser.log.
rem Zum Debuggen mit Konsole stattdessen:  .venv\Scripts\python.exe main.py
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" main.py %*
