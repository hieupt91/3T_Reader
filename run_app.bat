@echo off
setlocal
:: Clear extra paths to avoid DLL conflicts
set PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem
:: Activate virtual environment and run the app
call .venv\Scripts\activate.bat
python main.py
endlocal
