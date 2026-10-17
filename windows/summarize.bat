@echo off
rem Drag a sales file (.csv / .xlsx) onto this file to get the 5-line summary.
rem The result is also saved next to your file as  <name>-summary.txt
chcp 65001 >nul
if "%~1"=="" (
  py -m sales_summary_th --demo
) else (
  py -m sales_summary_th "%~1" --out "%~dpn1-summary.txt"
)
echo.
pause
