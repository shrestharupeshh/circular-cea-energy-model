@echo off
rem Double-click to start the Vertical Farming Energy Simulator.
title Vertical Farming Energy Simulator
cd /d "%~dp0"

rem Use the conda environment "cea" if conda is installed, otherwise whatever Python is on PATH.
for %%D in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%LOCALAPPDATA%\miniconda3" "C:\ProgramData\miniconda3" "C:\ProgramData\anaconda3") do (
  if exist "%%~D\Scripts\activate.bat" (
    call "%%~D\Scripts\activate.bat" "%%~D"
    call conda activate cea 2>nul
    goto :ready
  )
)
:ready
python --version >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Miniconda or Python 3.10+ and try again.
  pause
  exit /b 1
)

python -c "import streamlit, plotly, pandas, numpy" >nul 2>&1
if errorlevel 1 (
  echo Installing required packages, this happens only once...
  python -m pip install -r requirements.txt
)

echo.
echo Starting the simulator. It opens in your browser at http://localhost:8501
echo Keep this window open while you use it. Close it to stop the simulator.
echo.
python -m streamlit run app.py --browser.gatherUsageStats false
pause
