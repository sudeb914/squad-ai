@echo off
REM Build Squad AI for Windows. Run from the project root:  packaging\build.bat
setlocal
cd /d "%~dp0.."

echo ==^> Creating build venv
python -m venv .build-venv
call .build-venv\Scripts\activate.bat

echo ==^> Installing dependencies (+ PyInstaller)
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo ==^> Running tests before packaging
python -m unittest discover -s tests
if errorlevel 1 (
  echo Tests failed; aborting build.
  exit /b 1
)

echo ==^> Building with PyInstaller
pyinstaller --noconfirm packaging\squad_ai.spec

echo ==^> Done. Output in dist\SquadAI\
dir dist
endlocal
