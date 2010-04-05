@ECHO OFF

REM call maya and use standard unittest testrunner to run UI given tests

set BASE=%~dp0
set COLLECTED_ARGS=;

REM collect command line arguments and convert files into fully qualified path names
REM non filename arguments pass unchanged
REM NOTE:could not find a way to make it work without giving full pathname of the modules to python 2.5
REM      there was no way using python standard environment variables - thats why we do the hassle here
:collect
IF "%1"=="" goto argsDone 
	IF EXIST %1 (set COLLECTED_ARGS=%COLLECTED_ARGS%%~f1;) ELSE set COLLECTED_ARGS=%COLLECTED_ARGS%%1;
	SHIFT
	GOTO collect
:argsDone

REM prepare the environment to use a minimal UI - put mrv into the script path
REM as well as our helper script, but we create a command to hand over to cmd.exe
REM to keep the current environment clean
set COMMAND="set MAYA_SCRIPT_PATH=%BASE%;%BASE%..\..\..;%MAYA_SCRIPT_PATH%"
set COMMAND=%COMMAND%"&&set MRV_PYTHON_PATH=%BASE%..\..\.."
set COMMAND=%COMMAND%"&&set MAYA_OVERRIDE_UI=initialLayout_minimal.mel"
set COMMAND=%COMMAND%"&&set MAYA_TEST_ARGS=%COLLECTED_ARGS%"

REM assure we have no additional environment set
set MAYA_APP_TMP=%TMP%\maya_test_home
IF NOT EXIST %MAYA_APP_TMP% mkdir %MAYA_APP_TMP%
REM creating an empty Maya.env file
echo. 2>%MAYA_APP_DIR%\Maya.env

set COMMAND=%COMMAND%"&&set MAYA_APP_DIR=%MAYA_APP_TMP%&&maya"

REM cleaning %COMMAND% from unnecessary quotes we needed to create the command
set COMMAND="%COMMAND:"=%"

REM run
cmd /c %COMMAND%

:end