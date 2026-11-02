$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Get-PdvEnvValue([string]$Name) {
    $envFile = Join-Path $PSScriptRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile)) { return $null }
    $keyPattern = '^\s*{0}\s*=\s*(.*?)\s*$' -f [regex]::Escape($Name)
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $candidate = $line.TrimStart([char]0xFEFF)
        if ($candidate -match $keyPattern) {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'")))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

function Resolve-PdvPath([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    if ([IO.Path]::IsPathRooted($Value)) { return $Value }
    return Join-Path $PSScriptRoot $Value
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $elevatedArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-File', ('"' + $PSCommandPath + '"'))
    Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -ArgumentList $elevatedArgs
    exit 0
}
$pdvNodeSetting = $env:NODE_EXE
if (-not $pdvNodeSetting) { $pdvNodeSetting = Get-PdvEnvValue 'NODE_EXE' }
$pdvNodePath = Resolve-PdvPath $pdvNodeSetting
if (-not $pdvNodePath) {
    $pdvNodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($pdvNodeCommand) { $pdvNodePath = $pdvNodeCommand.Source }
}
if (-not $pdvNodePath) {
    $pdvNodePath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
if (-not (Test-Path -LiteralPath $pdvNodePath)) {
    throw 'Instale Node.js 22 ou superior e execute npm install e npm run build.'
}
$pdvPythonSetting = $env:PDV_PYTHON
if (-not $pdvPythonSetting) { $pdvPythonSetting = Get-PdvEnvValue 'PDV_PYTHON' }
$pdvPythonPath = Resolve-PdvPath $pdvPythonSetting
if (-not $pdvPythonPath) {
    $pdvPythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pdvPythonCommand -and $pdvPythonCommand.Source -notmatch '\\WindowsApps\\') {
        $pdvPythonPath = $pdvPythonCommand.Source
    }
}
if (-not $pdvPythonPath) {
    $pdvPythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pdvPythonLauncher) {
        $detectedPython = & $pdvPythonLauncher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $detectedPython) {
            $pdvPythonPath = ([string]$detectedPython).Trim()
        }
    }
}
if (-not $pdvPythonPath) {
    $pdvPythonRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $pdvPythonRuntime) { $pdvPythonPath = $pdvPythonRuntime }
}
if ($pdvPythonPath) {
    if (-not (Test-Path -LiteralPath $pdvPythonPath)) {
        throw "PDV_PYTHON não aponta para um executável existente: $pdvPythonPath"
    }
    $env:PDV_PYTHON = $pdvPythonPath
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) {
    throw 'O painel precisa ser compilado. Execute npm run build.'
}
$pdvPort = $env:PORT
if (-not $pdvPort) { $pdvPort = Get-PdvEnvValue 'PORT' }
if (-not $pdvPort) { $pdvPort = '4318' }
Write-Host "Abra http://127.0.0.1:$pdvPort. O assistente pode lançar itens no PDV e para antes do fechamento, pagamento e NFC-e."
& $pdvNodePath --env-file-if-exists=.env server/index.js
exit $LASTEXITCODE
