@echo off
set "STAR_OFFICE_UI_PATH=C:\Users\sbattaglia\Downloads\Star-Office-UI"

if not exist "%STAR_OFFICE_UI_PATH%" (
  echo Star Office UI folder not found:
  echo %STAR_OFFICE_UI_PATH%
  pause
  exit /b 1
)

cd /d "%STAR_OFFICE_UI_PATH%"

if not exist "node_modules" (
  echo node_modules not found. Running npm install...
  npm install
  if errorlevel 1 (
    echo npm install failed.
    pause
    exit /b 1
  )
)

echo Starting Star Office UI dev server...
npm run dev
if errorlevel 1 (
  echo npm run dev failed.
  pause
  exit /b 1
)
