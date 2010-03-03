@ECHO OFF

REM call maya and use standard unittest testrunner to run UI given tests

set base=%~dp0

REM prepare the environment to use a minimal UI - put mayarv into the script path
REM as well as our helper script
set COMMAND="set MAYA_SCRIPT_PATH=%base%;%base%..\..\..;%MAYA_SCRIPT_PATH%"
set COMMAND=%COMMAND%"&&set MAYARV_PYTHON_PATH=%base%..\..\.."
set COMMAND=%COMMAND%"&&set MAYA_OVERRIDE_UI=initialLayout_minimal.mel"

REM assure we have no additional environment set
set MAYA_APP_TMP=%TMP%\maya_test_home
IF NOT EXIST %MAYA_APP_TMP% mkdir %MAYA_APP_TMP%
echo. 2>%MAYA_APP_DIR%\Maya.env

set COMMAND=%COMMAND%"&&set MAYA_APP_DIR=%MAYA_APP_TMP%&&maya"

set COMMAND="%COMMAND:"=%"

cmd /c %COMMAND%

REM execute mayarv
REM cmd.exe /C "%basedir%..\..\start\mayarv.bat %basedir%\nosestartup.py" %*

:end	