@ECHO OFF

REM call mayapy with the nosetests startup script

set basedir=%~dp0
set mrvbase=%basedir%..\..\ext\mrv\

REM execute mrv
cmd.exe /C "%mrvbase%bin\mrv.bat %mrvbase%\bin\nosestartup.py" %*

:end	