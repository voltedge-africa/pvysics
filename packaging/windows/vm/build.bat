@echo off
set SHARE=\\host.lan\Data
set PATH=%USERPROFILE%\.local\bin;C:\Program Files (x86)\Inno Setup 6;%PATH%
set UV_PYTHON=3.13
rem A VM installed before this step existed has no Inno Setup, so the setup exe would be skipped: install it once.
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" curl.exe -fL -o C:\is.exe https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" C:\is.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
rmdir /S /Q C:\src 2>nul
mkdir C:\src
xcopy /E /I /H /Y "%SHARE%\src-tree\*" C:\src\
cd /d C:\src
echo --- building
uv run --group build python packaging/build.py
echo build exit code %ERRORLEVEL%
rmdir /S /Q "%SHARE%\out" 2>nul
mkdir "%SHARE%\out"
copy /Y dist\*.zip "%SHARE%\out\"
copy /Y dist\*-setup.exe "%SHARE%\out\"
echo finished %DATE% %TIME%
echo done > "%SHARE%\DONE"
