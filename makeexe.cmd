@echo off
echo.
echo In order to run this, you need to have the module py2exe installed into your python distribution.
echo.
echo You can download it from http://www.py2exe.org/
echo.
echo.
setlocal
	pushd %~dp0
		
		rmdir /s /q build > nul 2>&1
		rmdir /s /q bin > nul 2>&1
		
		python setup.py py2exe
	
	popd
endlocal
