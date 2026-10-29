$ErrorActionPreference = 'Stop'
$accountDirectory = $PSScriptRoot
$pythonExecutable = (Get-Command python.exe -ErrorAction Stop).Source
$pythonExecutable = Join-Path (Split-Path $pythonExecutable) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'pythonw.exe is required to run without a console window.' }
$launcher = Join-Path $accountDirectory 'startup_check.py'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonExecutable -Argument ('"' + $launcher + '"') -WorkingDirectory $accountDirectory
$signIn = New-ScheduledTaskTrigger -AtLogOn -User $identity
$signIn.Delay = 'PT90S'
# The inexpensive Python guard also covers sleep/resume or an already-on laptop.
$availability = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -Hidden
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger @($signIn, $availability) -Settings $settings -Principal $principal -Description 'Queue a managed FPL review only when due; uses the signed-in user, stores no password, does not wake the laptop.'
Register-ScheduledTask -TaskName 'FPL account catch-up' -InputObject $task -Force | Select-Object TaskName, State
# Open the desktop app at sign-in so the queued chat can use its FPL browser.
$codexApp = Get-StartApps | Where-Object { $_.AppID -eq 'OpenAI.Codex_2p2nqsd0c76g0!App' } | Select-Object -First 1
if (-not $codexApp) { throw 'Installed Codex desktop app could not be located for startup.' }
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'FPL Codex.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $env:WINDIR 'explorer.exe'
$shortcut.Arguments = 'shell:AppsFolder\' + $codexApp.AppID
$shortcut.Description = 'Open Codex for managed FPL catch-up reviews'
$shortcut.Save()
