# Native Windows bootstrap for the existing Python policy entry points.
# Invoked with -Command so PowerShell does not consume the hook's JSON stdin.
$ErrorActionPreference = 'Stop'

try {
    $scriptName = $args[0]
    if ($scriptName -notin @('lifecycle.py', 'shell_guard.py', 'review_native.py')) {
        throw 'Unknown policy entry point.'
    }
    $scriptArguments = @($args | Select-Object -Skip 1)

    $gitCommand = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue
    $gitPath = if ($gitCommand) { $gitCommand.Source } else { $null }
    if (-not $gitPath) {
        foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, "$env:LOCALAPPDATA\Programs")) {
            if (-not $base) { continue }
            $candidate = Join-Path $base 'Git\cmd\git.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $gitPath = $candidate; break }
        }
    }
    if (-not $gitPath) { throw 'Install Git for Windows, then restart Codex so git.exe is on PATH.' }
    $env:PATH = (Split-Path $gitPath) + ';' + $env:PATH

    $pythonPath = $null
    $pythonPrefix = @()
    $candidates = @()
    foreach ($name in @('python.exe', 'python3.exe', 'py.exe')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        # WindowsApps aliases can open an installer instead of running Python.
        if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') {
            $candidates += $command.Source
        }
    }
    foreach ($pattern in @("$env:LOCALAPPDATA\Python\pythoncore-*\python.exe",
                           "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
                           "$env:ProgramFiles\Python*\python.exe",
                           "$env:LOCALAPPDATA\Programs\Python\Launcher\py.exe",
                           "$env:SystemRoot\py.exe")) {
        $candidates += @(Get-Item -Path $pattern -ErrorAction SilentlyContinue |
                         Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName)
    }
    foreach ($candidate in $candidates) {
        $prefix = if ((Split-Path $candidate -Leaf) -eq 'py.exe') { @('-3') } else { @() }
        & $candidate @prefix -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonPath = $candidate; $pythonPrefix = $prefix; break }
    }
    if (-not $pythonPath) { throw 'Install Python 3.9+ (python.org), then restart Codex or add Python to PATH.' }

    $repoRoot = & $gitPath rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0) { throw 'Open a trusted Git worktree in Codex; git rev-parse failed.' }
    $entryPoint = Join-Path $repoRoot ".ai/scripts/$scriptName"
    if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
        throw "Missing $entryPoint; reinstall the project-local AGENTIC kit."
    }
    $env:PYTHONUTF8 = '1'
    & $pythonPath @pythonPrefix $entryPoint @scriptArguments
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine('AGENTIC Windows hook: ' + $_.Exception.Message)
    exit 2
}
