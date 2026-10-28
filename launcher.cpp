#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR CommandLine, int)
{
    wchar_t path[32768];
    GetModuleFileNameW(nullptr, path, 32768);
    std::wstring folder(path);
    folder.resize(folder.find_last_of(L"\\/"));
    std::wstring python = folder + L"\\runtime\\pythonw.exe";
    if (GetFileAttributesW(python.c_str()) == INVALID_FILE_ATTRIBUTES)
    {
        python = folder + L"\\.venv\\Scripts\\pythonw.exe";
    }
    std::wstring command = L"\"" + python + L"\" \"" + folder + L"\\app.py\" " + CommandLine;
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(python.c_str(), command.data(), nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW, nullptr, folder.c_str(), &startup, &process))
    {
        MessageBoxW(nullptr, L"Could not start the editor. Extract the entire archive and keep the runtime folder and app.py beside this executable.",
                    L"Clothing Mesh Editor", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
