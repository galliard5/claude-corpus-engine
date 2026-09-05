@echo off
REM refresh_indexes.bat — Rebuilds all corpus indexes in dependency order.
REM Sequential execution: each step must succeed before the next runs.
REM Double-click from Python/ in Explorer to run.
REM
REM FIRST RUN: this works as-is from any install location — the cd below moves to
REM this script's own directory, so build_indexes.py is invoked by bare filename.
REM Only replace it with an absolute path if you need to launch this .bat from a
REM shortcut or scheduler that cannot set the working directory.
REM
REM What build_indexes.py indexes is a separate question: it reads root_directory
REM from indexer.cfg (or CORPUS_ROOT, which wins if set). Point that at your corpus
REM before the first run, or the indexes will be built for the wrong tree.

setlocal
cd /d "%~dp0"

echo.
echo === Building directory and search indexes (all files from one walk)...
python build_indexes.py --no-pause --check-schemas
if errorlevel 1 (
    echo.
    echo [FAIL] build_indexes.py exited with errors.
    pause
    exit /b 1
)

echo.
echo === All indexes refreshed successfully.
echo.
pause
