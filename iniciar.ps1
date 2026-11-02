$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $elevatedArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-File', ('"' + $PSCommandPath + '"'))
    Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -Verb RunAs -ArgumentList $elevatedArgs
    exit 0
}
$pdvNodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($pdvNodeCommand) {
    $pdvNodePath = $pdvNodeCommand.Source
} else {
    $pdvNodePath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
if (-not (Test-Path -LiteralPath $pdvNodePath)) {
    throw 'Instale Node.js 22 ou superior e execute npm install e npm run build.'
}
$pdvPythonRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if ((-not $env:PDV_PYTHON) -and (Test-Path -LiteralPath $pdvPythonRuntime)) {
    $env:PDV_PYTHON = $pdvPythonRuntime
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) {
    throw 'O painel precisa ser compilado. Execute npm run build.'
}
Write-Host 'Abra http://127.0.0.1:4318. O assistente pode lançar itens no PDV e para antes do fechamento, pagamento e NFC-e.'
& $pdvNodePath --env-file-if-exists=.env server/index.js
exit $LASTEXITCODE
