@echo off
rem Runs once, after Windows is installed. Installs the tools, then builds; it also leaves a poller that runs
rem run.bat from the shared folder, so the build can be repeated without reinstalling Windows.
set SHARE=\\host.lan\Data
set LOG=%SHARE%\build.log
echo started %DATE% %TIME% > "%LOG%"
schtasks /Create /F /SC MINUTE /MO 1 /TN pvysics-poll /TR "cmd /c if exist %SHARE%\run.bat (move /Y %SHARE%\run.bat C:\run-now.bat & call C:\run-now.bat >> %SHARE%\build.log 2>&1)" >> "%LOG%" 2>&1
echo --- installing uv >> "%LOG%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" >> "%LOG%" 2>&1
echo --- installing Inno Setup >> "%LOG%"
curl.exe -fL -o C:\is.exe https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe >> "%LOG%" 2>&1
C:\is.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- >> "%LOG%" 2>&1
copy /Y "%SHARE%\run.bat.initial" C:\run-now.bat >> "%LOG%" 2>&1
call C:\run-now.bat >> "%LOG%" 2>&1
