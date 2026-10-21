#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>
#include <wctype.h>
#include <stdlib.h>

static BOOL WINAPI keep_waiting(DWORD event) {
    return event == CTRL_C_EVENT || event == CTRL_BREAK_EVENT;
}

int wmain(void) {
    wchar_t directory[32768];
    DWORD length = GetModuleFileNameW(NULL, directory, 32768);
    if (!length || length >= 32768) return 2;
    wchar_t *name = wcsrchr(directory, L'\\');
    if (!name) return 2;
    const wchar_t *module = _wcsicmp(name + 1, L"pyao-server-indicator.exe") == 0
        ? L"src.desktop.indicator" : L"src.run_server";
    *name = L'\0';
    /* Windows treats argv[0] specially; filenames cannot contain a quote. */
    const wchar_t *tail = GetCommandLineW();
    while (iswspace(*tail)) ++tail;
    if (*tail == L'"') {
        ++tail;
        while (*tail && *tail != L'"') ++tail;
        if (*tail) ++tail;
    } else {
        while (*tail && !iswspace(*tail)) ++tail;
    }
    size_t capacity = wcslen(directory) + wcslen(tail) + 128;
    wchar_t *command = calloc(capacity, sizeof(wchar_t));
    if (!command) return 2;
    int formatted = _snwprintf_s(command, capacity, _TRUNCATE,
        L"\"%ls\\python\\python.exe\" -I -B -X utf8 -m %ls %ls", directory, module, tail);
    if (formatted < 0) { free(command); return 2; }
    SetEnvironmentVariableW(L"PYTHONPATH", NULL);
    SetEnvironmentVariableW(L"PYTHONHOME", NULL);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE", L"1");
    SetConsoleCtrlHandler(keep_waiting, TRUE);
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION child = {0};
    startup.cb = sizeof(startup);
    BOOL created = CreateProcessW(NULL, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &child);
    free(command);
    if (!created) return 2;
    CloseHandle(child.hThread);
    WaitForSingleObject(child.hProcess, INFINITE);
    DWORD status = 2;
    GetExitCodeProcess(child.hProcess, &status);
    CloseHandle(child.hProcess);
    return (int)status;
}
