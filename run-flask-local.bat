@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m app.main > flask-server.out 2> flask-server.err
