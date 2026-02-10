@echo off
chcp 65001 >nul
echo ========================================
echo    Glitch Maker - Compilation .exe
echo ========================================
echo.

REM S'assurer qu'on est dans le bon dossier (celui du .bat)
cd /d "%~dp0"

echo [1/3] Installation des dependances...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERREUR installation
    pause
    exit /b 1
)

echo.
echo [2/3] Compilation avec PyInstaller...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "GlitchMaker" ^
    --add-data "assets;assets" ^
    --add-data "lang;lang" ^
    --add-data "effects;effects" ^
    --add-data "plugins;plugins" ^
    --hidden-import sounddevice ^
    --hidden-import soundfile ^
    --hidden-import numpy ^
    --hidden-import scipy ^
    --hidden-import scipy.signal ^
    --hidden-import pydub ^
    --hidden-import librosa ^
    --hidden-import librosa.util ^
    --hidden-import lameenc ^
    --hidden-import plugins ^
    --hidden-import plugins.loader ^
    --hidden-import plugins.preview_player ^
    --hidden-import plugins.user_loader ^
    --hidden-import effects.effect_bitcrusher ^
    --hidden-import effects.effect_buffer_freeze ^
    --hidden-import effects.effect_chorus ^
    --hidden-import effects.effect_datamosh ^
    --hidden-import effects.effect_delay ^
    --hidden-import effects.effect_distortion ^
    --hidden-import effects.effect_filter ^
    --hidden-import effects.effect_granular ^
    --hidden-import effects.effect_ott ^
    --hidden-import effects.effect_pan ^
    --hidden-import effects.effect_phaser ^
    --hidden-import effects.effect_pitch_shift ^
    --hidden-import effects.effect_reverse ^
    --hidden-import effects.effect_ring_mod ^
    --hidden-import effects.effect_saturation ^
    --hidden-import effects.effect_shuffle ^
    --hidden-import effects.effect_stutter ^
    --hidden-import effects.effect_tape_stop ^
    --hidden-import effects.effect_time_stretch ^
    --hidden-import effects.effect_tremolo ^
    --hidden-import effects.effect_vinyl ^
    --hidden-import effects.effect_volume ^
    main.py

if %errorlevel% neq 0 (
    echo ERREUR compilation
    pause
    exit /b 1
)

echo.
echo [3/3] Nettoyage...
rmdir /S /Q build >nul 2>&1
del /Q GlitchMaker.spec >nul 2>&1

echo.
echo ========================================
echo    OK : dist\GlitchMaker.exe
echo ========================================
echo.
echo Le .exe se trouve dans le dossier dist\
echo Au premier lancement, un dossier data\ sera
echo cree a cote du .exe pour stocker vos donnees.
pause
