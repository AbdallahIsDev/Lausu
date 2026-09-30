/*
 * linker_wrap.c: MSYS2/mingw-w64 linker wrapper for the x86_64-pc-windows-gnu
 * target (the toolchain used on Windows dev machines that have no MSVC).
 *
 * This file is TRACKED IN GIT. It is the single source of truth for the
 * GNU-target linker shim; scripts/build/ensure_gnu_linkchain.py compiles it
 * to src-tauri/.toolchain/linker-wrap.exe and generates the matching
 * src-tauri/.cargo/config.toml. Nothing here is machine-specific: the MSYS2
 * install is DISCOVERED at runtime (MINGW_GCC env override, then the usual
 * install roots, then PATH), so the same source works on any Windows
 * GNU-toolchain machine. That portability is what makes it safe to commit.
 *
 * Problem 1 - absolute @response files. When rustc's linker command line is
 * long it writes the args to a response file and passes `@C:\abs\path`. MSYS2
 * gcc does not expand absolute @-files itself; it forwards the `@...` token to
 * ld, which has no response-file support at all -> `ld.exe: cannot find @...:
 * Invalid argument`. Fix: copy the response file next to this executable,
 * chdir() there, and re-pass it as a RELATIVE `@link-<pid>.rsp`, which gcc
 * demonstrably expands itself. Everything resolves from GetModuleFileNameA, so
 * it works regardless of the CWD cargo/rustc spawned us with.
 *
 * Problem 2 - rustc deletes codegen artifacts mid-link. rustc spawns the
 * linker and then asynchronously deletes the per-crate temp dir
 * (`debug\deps\rustcXXXX\`) AND every `*.rcgu.o` in `debug\deps\`. With a slow
 * linker (MSYS2 gcc -> collect2 -> ld) the deletion wins the race: the objects
 * vanish, the link fails, and because rustc does not wait for the linker,
 * rustc still exits 0 and cargo marks the crate built even though its DLL does
 * not exist. Fix: while the files still exist, copy every referenced temp
 * artifact (`*.rcgu.o`, `symbols.o`, `list.def`, `rmeta.o`) into
 * `obj-<pid>/` and rewrite the response file to point at the copies.
 *
 * Problem 3 - the obj-<pid>/ copies used to leak forever. `_execvp` REPLACES
 * this process image with gcc, so no code here ever ran again to delete them
 * (~64 MB per link, 24 GB accumulated). The linker is now started with
 * `_spawnvp(_P_WAIT)`: identical command line and exit status, but this
 * process survives to reap its own scratch dir in cleanup_scratch().
 *
 * Short links (no @arg) pass through untouched.
 *
 * Diagnostics: every invocation is appended to <exe dir>/linker-wrap.log,
 * capped at LOG_MAX_BYTES so the log cannot become its own disk leak. Set
 * LW_DEBUG=1 for stderr output too (visible only when a link fails, because
 * rustc swallows linker stderr on success).
 */
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <process.h>
#include <stdlib.h>
#include <errno.h>
#include <direct.h>

#define LOG_MAX_BYTES (2 * 1024 * 1024)

static int dbg = 0;
static char g_dir[MAX_PATH];   /* this executable's directory (absolute)  */
static char g_dst[MAX_PATH];   /* absolute path of our rsp copy         */
static char g_log[MAX_PATH];   /* absolute path of the log file         */
static char g_objdir[MAX_PATH];/* absolute path of our obj-<pid> dir    */
static char g_gcc[MAX_PATH];   /* absolute path of the real gcc.exe     */
static char g_prefix[MAX_PATH];/* GCC_EXEC_PREFIX derived from g_gcc    */
static char g_bindir[MAX_PATH];/* bin dir derived from g_gcc             */

static int file_exists(const char *p) {
    DWORD a = GetFileAttributesA(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

/* Append one diagnostic line. The log lives in a gitignored dir that nothing
 * else prunes, so it is size-capped: without this it becomes its own slow disk
 * leak (it reached 17 MB before the cap existed). */
static void logmsg(const char *fmt, const char *s1, int n) {
    FILE *lf = fopen(g_log, "a");
    if (lf) {
        fseek(lf, 0, SEEK_END);
        if (ftell(lf) > LOG_MAX_BYTES) {
            fclose(lf);
            lf = fopen(g_log, "w");   /* rotate: drop the stale log */
        }
        if (lf) {
            fprintf(lf, "[linker-wrap pid=%lu] ", (unsigned long)GetCurrentProcessId());
            fprintf(lf, fmt, s1, n);
            fprintf(lf, "\n");
            fclose(lf);
        }
    }
    if (!dbg) return;
    fprintf(stderr, "[linker-wrap] ");
    fprintf(stderr, fmt, s1, n);
    fprintf(stderr, "\r\n");
    fflush(stderr);
}

/* Copy src (a Windows absolute path, backslash or forward slash) to
 * dst (absolute). Returns bytes copied, or -1 on failure. */
static long copy_file(const char *src, const char *dst) {
    HANDLE hin = CreateFileA(src, GENERIC_READ, FILE_SHARE_READ, NULL,
                             OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hin == INVALID_HANDLE_VALUE) {
        logmsg("read open failed src=%s err=%lu", src, (int)GetLastError());
        return -1;
    }
    LARGE_INTEGER sz;
    if (!GetFileSizeEx(hin, &sz) || sz.QuadPart > (LONG64)64 * 1024 * 1024) {
        CloseHandle(hin);
        logmsg("bad size src=%s", src, 0);
        return -1;
    }
    char *buf = (char *)malloc((size_t)sz.QuadPart);
    if (!buf) { CloseHandle(hin); return -1; }
    DWORD rd = 0;
    BOOL ok = ReadFile(hin, buf, (DWORD)sz.QuadPart, &rd, NULL);
    CloseHandle(hin);
    if (!ok || rd != (DWORD)sz.QuadPart) {
        logmsg("read failed src=%s rd=%lu", src, (int)rd);
        free(buf);
        return -1;
    }
    HANDLE hout = CreateFileA(dst, GENERIC_WRITE, 0, NULL,
                              CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hout == INVALID_HANDLE_VALUE) {
        logmsg("write open failed dst=%s err=%lu", dst, (int)GetLastError());
        free(buf);
        return -1;
    }
    DWORD wr = 0;
    ok = WriteFile(hout, buf, rd, &wr, NULL);
    CloseHandle(hout);
    free(buf);
    if (!ok || wr != rd) {
        logmsg("write failed dst=%s wr=%lu", dst, (int)wr);
        return -1;
    }
    return (long)rd;
}

/* gcc derives its install tree from argv[0], and needs GCC_EXEC_PREFIX and
 * its bin dir on PATH to find collect2 / ld / as / cc1. Derive all three from
 * the discovered gcc path so no path is baked into this source. */
static void adopt_gcc(const char *path) {
    snprintf(g_gcc, sizeof g_gcc, "%s", path);
    snprintf(g_bindir, sizeof g_bindir, "%s", path);
    char *slash = strrchr(g_bindir, '\\');
    if (!slash) slash = strrchr(g_bindir, '/');
    if (slash) *slash = '\0';                     /* ...\mingw64\bin      */

    char root[MAX_PATH];
    snprintf(root, sizeof root, "%s", g_bindir);
    slash = strrchr(root, '\\');
    if (!slash) slash = strrchr(root, '/');
    if (slash) slash[1] = '\0';                   /* ...\mingw64\         */
    snprintf(g_prefix, sizeof g_prefix, "%slib/gcc/", root);
}

/* Locate the real gcc. Order: explicit MINGW_GCC override, then the standard
 * MSYS2 / mingw install roots, then PATH. Returns 0 on success. */
static int find_gcc(void) {
    const char *env = getenv("MINGW_GCC");
    if (env && *env && file_exists(env)) { adopt_gcc(env); return 0; }

    static const char *roots[] = {
        "C:\\msys64\\mingw64\\bin\\x86_64-w64-mingw32-gcc.exe",
        "C:\\msys64\\ucrt64\\bin\\x86_64-w64-mingw32-gcc.exe",
        "C:\\msys64\\clang64\\bin\\x86_64-w64-mingw32-gcc.exe",
        "C:\\msys64\\mingw32\\bin\\x86_64-w64-mingw32-gcc.exe",
        "C:\\mingw64\\bin\\x86_64-w64-mingw32-gcc.exe",
        "C:\\ProgramData\\chocolatey\\bin\\x86_64-w64-mingw32-gcc.exe",
    };
    for (size_t i = 0; i < sizeof roots / sizeof roots[0]; i++) {
        if (file_exists(roots[i])) { adopt_gcc(roots[i]); return 0; }
    }

    const char *path = getenv("PATH");
    if (path) {
        static const char *leaf = "x86_64-w64-mingw32-gcc.exe";
        char buf[MAX_PATH];
        const char *p = path;
        while (*p) {
            const char *sep = strchr(p, ';');
            size_t n = sep ? (size_t)(sep - p) : strlen(p);
            if (n && n + strlen(leaf) + 2 < sizeof buf) {
                memcpy(buf, p, n);
                buf[n] = '\\';
                snprintf(buf + n + 1, sizeof buf - n - 1, "%s", leaf);
                if (file_exists(buf)) { adopt_gcc(buf); return 0; }
            }
            if (!sep) break;
            p = sep + 1;
        }
    }
    fprintf(stderr,
            "[linker-wrap] cannot find x86_64-w64-mingw32-gcc.exe. Install "
            "MSYS2 (https://www.msys2.org/) or set MINGW_GCC to its full "
            "path.\r\n");
    return -1;
}

/* Copy src to g_dst (the wrapper-dir rsp copy). */
static long copy_rsp(const char *src) {
    return copy_file(src, g_dst);
}

/* True if `path` (un-escaped, single backslashes or forward slashes) is a
 * rustc codegen temp artifact that gets deleted asynchronously after the
 * linker is spawned. */
static int is_temp_artifact(const char *path) {
    size_t len = strlen(path);
    static const char *suffixes[] = {".rcgu.o", "symbols.o", "list.def", "rmeta.o"};
    size_t i;
    for (i = 0; i < sizeof(suffixes) / sizeof(suffixes[0]); i++) {
        size_t sl = strlen(suffixes[i]);
        if (len >= sl && _stricmp(path + len - sl, suffixes[i]) == 0) return 1;
    }
    return 0;
}

/* Un-escape a path line from the rsp: rustc writes `C:\\dir\\file` (doubled
 * backslashes). Convert to `C:\dir\file` in place. Also strip a leading
 * `-Wl,` (gcc driver passthrough marker), returns 1 if it was present and
 * shifts the path start. */
static char *unescape_path(char *line, int *had_wl) {
    char *p, *q;
    *had_wl = 0;
    if (strncmp(line, "-Wl,", 4) == 0) {
        *had_wl = 1;
        line += 4;
    }
    p = line;
    for (q = line; *p; p++) {
        if (*p == '\\' && p[1] == '\\') { *q++ = '\\'; p++; }
        else *q++ = *p;
    }
    *q = '\0';
    return line;
}

/* Parse the copied rsp (g_dst), copy every referenced temp artifact into
 * <g_dir>/obj-<pid>/, and rewrite g_dst in place to point at the copies.
 * Returns 0 on success (even if nothing needed copying), -1 on failure. */
static int preserve_artifacts(void) {
    char objdir[MAX_PATH];
    snprintf(objdir, sizeof objdir, "%s\\obj-%lu", g_dir,
             (unsigned long)GetCurrentProcessId());
    CreateDirectoryA(objdir, NULL);
    snprintf(g_objdir, sizeof g_objdir, "%s", objdir);

    char tmpin[MAX_PATH];
    char tmpout[MAX_PATH];
    snprintf(tmpin, sizeof tmpin, "%s\\link-%lu.in", g_dir,
             (unsigned long)GetCurrentProcessId());
    snprintf(tmpout, sizeof tmpout, "%s\\link-%lu.fixed", g_dir,
             (unsigned long)GetCurrentProcessId());
    if (!CopyFileA(g_dst, tmpin, FALSE)) {
        logmsg("preserve: cannot stage rsp %s err=%lu", g_dst, (int)GetLastError());
        return -1;
    }

    FILE *fin = fopen(tmpin, "r");
    if (!fin) { logmsg("preserve: open rsp %s failed errno=%d", tmpin, errno); return -1; }
    FILE *fout = fopen(tmpout, "w");
    if (!fout) { fclose(fin); logmsg("preserve: open rsp %s failed errno=%d", tmpout, errno); return -1; }

    char line[16384];
    int rc = 0;
    while (fgets(line, sizeof line, fin)) {
        size_t l = strlen(line);
        while (l > 0 && (line[l - 1] == '\n' || line[l - 1] == '\r')) line[--l] = '\0';
        char work[16384];
        memcpy(work, line, l + 1);
        int had_wl = 0;
        char *path = unescape_path(work, &had_wl);
        if (*path && is_temp_artifact(path)) {
            const char *base = path;
            for (const char *scan = path; *scan; scan++) {
                if (*scan == '\\' || *scan == '/') base = scan + 1;
            }
            if (*base) {
                char dst[MAX_PATH];
                snprintf(dst, sizeof dst, "%s\\%s", objdir, base);
                long n = copy_file(path, dst);
                if (n >= 0) {
                    /* gcc's rsp parser treats `\` as an escape and strips
                     * single backslashes (`C:\Users` -> `C:Users`). The
                     * original rustc rsp doubles them; do the same. */
                    char esc[MAX_PATH * 2 + 8];
                    char *q = esc;
                    const char *p;
                    for (p = dst; *p && (size_t)(q - esc) < sizeof esc - 2; p++) {
                        if (*p == '\\') { *q++ = '\\'; *q++ = '\\'; }
                        else *q++ = *p;
                    }
                    *q = '\0';
                    if (had_wl) fprintf(fout, "-Wl,%s\n", esc);
                    else fprintf(fout, "%s\n", esc);
                } else {
                    /* Keep the original line and let gcc report the failure. */
                    fprintf(fout, "%s\n", line);
                }
                continue;
            }
        }
        fprintf(fout, "%s\n", line);
    }
    fclose(fin);
    fclose(fout);

    if (!CopyFileA(tmpout, g_dst, FALSE)) rc = -1;
    DeleteFileA(tmpin);
    DeleteFileA(tmpout);
    return rc;
}

/* Recursively delete `path` (file or directory). Best effort: a failure here
 * must never turn a successful link into a failed one. */
static void remove_tree(const char *path) {
    if (!path || !*path) return;
    DWORD attr = GetFileAttributesA(path);
    if (attr == INVALID_FILE_ATTRIBUTES) return;
    if (!(attr & FILE_ATTRIBUTE_DIRECTORY)) { DeleteFileA(path); return; }

    char pattern[MAX_PATH];
    snprintf(pattern, sizeof pattern, "%s\\*", path);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(pattern, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
            char child[MAX_PATH];
            snprintf(child, sizeof child, "%s\\%s", path, fd.cFileName);
            remove_tree(child);
        } while (FindNextFileA(h, &fd));
        FindClose(h);
    }
    /* Read-only leftovers would make RemoveDirectory fail and leak the dir. */
    SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);
    RemoveDirectoryA(path);
}

/* Drop everything this invocation created: the obj-<pid>/ copies, the
 * link-<pid>.rsp copy and any staged rsp leftovers. Runs once the linker has
 * exited, so the objects are provably no longer being read. */
static void cleanup_scratch(void) {
    remove_tree(g_objdir);
    g_objdir[0] = '\0';
    if (g_dst[0]) { DeleteFileA(g_dst); g_dst[0] = '\0'; }
    unsigned long pid = (unsigned long)GetCurrentProcessId();
    char tmp[MAX_PATH];
    snprintf(tmp, sizeof tmp, "%s\\link-%lu.in", g_dir, pid);   DeleteFileA(tmp);
    snprintf(tmp, sizeof tmp, "%s\\link-%lu.fixed", g_dir, pid); DeleteFileA(tmp);
}

int main(int argc, char **argv) {
    dbg = getenv("LW_DEBUG") != NULL;

    /* Resolve our own directory; everything else is relative to it. */
    if (!GetModuleFileNameA(NULL, g_dir, MAX_PATH)) {
        fprintf(stderr, "[linker-wrap] GetModuleFileNameA failed\r\n");
        return 127;
    }
    char *slash = strrchr(g_dir, '\\');
    if (!slash) slash = strrchr(g_dir, '/');
    if (slash) *slash = '\0';
    snprintf(g_dst, sizeof g_dst, "%s\\link-%lu.rsp", g_dir,
             (unsigned long)GetCurrentProcessId());
    snprintf(g_log, sizeof g_log, "%s\\linker-wrap.log", g_dir);

    if (find_gcc() != 0) return 127;

    /* Find an @response-file arg. rustc passes at most one. */
    int i;
    const char *src = NULL;
    for (i = 1; i < argc; i++) {
        if (argv[i][0] == '@') { src = argv[i] + 1; break; }
    }
    logmsg("invoked src=%s argc=%d", src ? src : "<no @arg>", argc);

    if (src) {
        long n = copy_rsp(src);
        if (n >= 0) {
            /* Copy the codegen temp artifacts BEFORE they are deleted, then
             * rewrite the rsp to point at the stable copies. */
            preserve_artifacts();
            /* chdir to our dir so the RELATIVE @arg below resolves (gcc
             * expands relative @files itself; absolute ones are forwarded to
             * ld, which is the bug we work around). */
            _chdir(g_dir);
            /* STATIC buffer: argv[i] must stay valid past the end of this
             * block, and a block-scoped local's stack slot gets reused by
             * later frames. */
            static char rsp_arg[MAX_PATH + 8];
            snprintf(rsp_arg, sizeof rsp_arg, "@link-%lu.rsp",
                     (unsigned long)GetCurrentProcessId());
            argv[i] = rsp_arg;
        }
    }

    /* Restore gcc's view of its install tree: argv[0] must carry the full
     * path (gcc derives exec_prefix from it), plus GCC_EXEC_PREFIX + PATH
     * as belt-and-braces for subprograms (collect2 / ld / as). */
    argv[0] = g_gcc;
    SetEnvironmentVariableA("GCC_EXEC_PREFIX", g_prefix);
    {
        const char *old_path = getenv("PATH");
        char new_path[4096];
        snprintf(new_path, sizeof new_path, "%s;%s", g_bindir,
                 old_path ? old_path : "");
        SetEnvironmentVariableA("PATH", new_path);
    }

    /* _spawnvp(_P_WAIT) instead of _execvp: _execvp OVERLAYS this process with
     * gcc, so nothing below could run and the obj-<pid>/ copies leaked on
     * every link. Same command line and exit status, but we survive to reap
     * our own scratch dir. The child inherits the console, so rustc still
     * captures gcc's stderr exactly as before. */
    intptr_t rc = _spawnvp(_P_WAIT, g_gcc, (const char *const *)argv);
    cleanup_scratch();
    if (rc == -1) {
        fprintf(stderr, "[linker-wrap] spawnvp failed errno=%d\r\n", errno);
        return 127;
    }
    return (int)rc;
}
