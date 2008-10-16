@echo off
setlocal
	pushd %~dp0
		
		if "%1" == "" (
			echo Usage: makedist ^<zipfilename^>
			goto :EOF
		)
		set ZIPFILE=%1

		call makeexe.cmd
		
		python makedist.py "%ZIPFILE%"
	
	popd
endlocal
