$adapters = Get-NetAdapter -Name 'Ethernet', 'Wi-Fi'
foreach ($adapter in $adapters) {
    $instanceId = $adapter.InstanceID
    $regPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$instanceId\Device Parameters"
    if (Test-Path $regPath) {
        Set-ItemProperty -Path $regPath -Name "PnPCapabilities" -Value 24 -Type DWord -Force -ErrorAction SilentlyContinue
        Write-Host "Updated registry for: $($adapter.Name) ($instanceId)"
    } else {
        Write-Host "Registry path not found for: $($adapter.Name) ($instanceId)"
    }
}

# Also check NDIS power management
$classGuid = "{4d36e972-e325-11ce-bfc1-08002be10318}"
$classPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\$classGuid"
if (Test-Path $classPath) {
    Get-ChildItem $classPath | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath
        if ($props.DriverDesc -match "Intel.*Ethernet|Intel.*Wireless|Intel.*Wi-Fi|Intel.*Dual Band") {
            Set-ItemProperty $_.PSPath -Name "PnPCapabilities" -Value 24 -Type DWord -Force -ErrorAction SilentlyContinue
            Write-Host "Updated class registry for: $($props.DriverDesc)"
        }
    }
}