@ECHO OFF

REM call mayapy with the nosetests startup script

set basedir=%~dp0

REM execute mayarv
cmd.exe /C "%basedir%..\..\..\mayarv\bin\mrv.bat %basedir%\nosestartup.py" %*

:end	