@echo off
chcp 65001 > NUL
echo ============================================================
echo   Сборка автономного исполняемого файла MALVIK-LABEL.exe
echo ============================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден! Установите Python 3.10+ и добавьте его в PATH.
    pause
    exit /b 1
)

echo [1/3] Установка зависимостей и PyInstaller...
pip install -r requirements.txt pyinstaller openpyxl

echo.
echo [2/3] Запуск сборки EXE через PyInstaller...
pyinstaller MALVIK-LABEL.spec --noconfirm

echo.
echo [3/3] Сборка успешно завершена!
echo Файл MALVIK-LABEL.exe находится в папке dist\
echo Этот файл можно переносить и запускать на любом компьютере без установки Python.
echo.
pause
