@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo Python introuvable. Installe Python depuis https://www.python.org/downloads/
    echo puis relance ce script.
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

python -m PyInstaller --noconfirm --onefile --windowed --paths . --collect-all tkinterdnd2 --collect-all sv_ttk --icon rkarrousel\assets\icon.ico --add-data "rkarrousel\assets;rkarrousel\assets" --name RKarrousel rkarrousel\__main__.py

echo.
echo Build termine. L'executable se trouve dans dist\RKarrousel.exe
endlocal
