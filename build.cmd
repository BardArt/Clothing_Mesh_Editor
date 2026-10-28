@echo off
setlocal
cd /d "%~dp0"
set "vswhere=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%vswhere%" (
    echo Visual Studio Build Tools with Desktop development with C++ are required to build.
    exit /b 1
)
set "vsPath="
for /f "usebackq delims=" %%i in (`"%vswhere%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "vsPath=%%i"
if not defined vsPath (
    echo Visual Studio C++ build tools were not found.
    exit /b 1
)
"%vsPath%\MSBuild\Current\Bin\MSBuild.exe" ClothingMeshEditor.sln /m /p:Configuration=Release /p:Platform=x64 %*
exit /b %errorlevel%
