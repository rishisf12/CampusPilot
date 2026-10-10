$adapters = Get-NetAdapter -Name 'Ethernet', 'Wi-Fi'
foreach ($a in $adapters) {
    $a | Set-NetAdapterPowerManagement -WakeOnPattern Enabled -WakeOnMagicPacket Enabled -WakeOnLinkChange Enabled -ErrorAction SilentlyContinue
    Write-Host "Configured: $($a.Name)"
}