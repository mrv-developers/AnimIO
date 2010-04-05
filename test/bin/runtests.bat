@ECHO OFF

REM call mayapy with the nosetests startup script

set basedir=%~dp0

REM execute mrv
cmd.exe /C "%basedir%..\..\..\mrv\bin\mrv.bat %basedir%\nosestartup.py" %*

:end	