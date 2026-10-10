<# 
  Keep-Awake Script for OpenCode / Long-running Tasks
  Run this in a SEPARATE terminal tab while OpenCode works.
  Press Ctrl+C to stop and restore normal sleep behavior.
#>

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class PowerManager {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    
    public const uint ES_CONTINUOUS      = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;
    public const uint ES_AWAYMODE_REQUIRED = 0x00000040;
}
'@

function Keep-Awake {
    Write-Host "=" * 60
    Write-Host "  KEEP AWAKE ACTIVE - Laptop will NOT sleep/hibernate"
    Write-Host "  Press Ctrl+C to stop and restore normal behavior"
    Write-Host "=" * 60
    Write-Host ""
    
    # Prevent sleep + keep display on + away mode
    $flags = [PowerManager]::ES_CONTINUOUS -bor [PowerManager]::ES_SYSTEM_REQUIRED -bor [PowerManager]::ES_DISPLAY_REQUIRED -bor [PowerManager]::ES_AWAYMODE_REQUIRED
    [PowerManager]::SetThreadExecutionState($flags) | Out-Null
    
    $startTime = Get-Date
    try {
        while ($true) {
            $elapsed = (Get-Date) - $startTime
            $elapsedStr = "{0:D2}h:{1:D2}m:{2:D2}s" -f $elapsed.Hours, $elapsed.Minutes, $elapsed.Seconds
            Write-Host "`r  Running for: $elapsedStr  |  Sleep: BLOCKED  |  Display: ON  " -NoNewline
            Start-Sleep -Seconds 10
        }
    }
    finally {
        # Restore normal behavior
        [PowerManager]::SetThreadExecutionState([PowerManager]::ES_CONTINUOUS) | Out-Null
        Write-Host ""
        Write-Host ""
        Write-Host "=" * 60
        Write-Host "  Keep-awake STOPPED - Normal sleep behavior restored"
        Write-Host "=" * 60
    }
}

Keep-Awake