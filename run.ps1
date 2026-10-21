$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $projectRoot '.venv\Scripts\python.exe'))) {
    py -3 -m venv (Join-Path $projectRoot '.venv')
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m pip install -r (Join-Path $projectRoot 'requirements.txt')
}
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $projectRoot 'app.py')
