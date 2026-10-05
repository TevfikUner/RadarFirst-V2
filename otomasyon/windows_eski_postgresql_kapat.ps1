#Requires -RunAsAdministrator
# Docker'a geçildikten sonra Windows'ta kalan yerel PostgreSQL kurulumlarını
# etkisizleştirir: servisler durdurulup "Devre dışı" yapılır, gelen bağlantıya
# izin veren "PostgreSQL Server" güvenlik duvarı kuralları silinir. Veri klasörü
# ve program dosyalarına dokunulmaz (kaldırmak için: Ayarlar > Uygulamalar).
# Yönetici PowerShell'de: powershell -ExecutionPolicy Bypass -File otomasyon\windows_eski_postgresql_kapat.ps1

Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Service -Name $_.Name -Force -ErrorAction SilentlyContinue
    Set-Service -Name $_.Name -StartupType Disabled
    Write-Host "Servis devre disi: $($_.Name)"
}

$kurallar = Get-NetFirewallRule -DisplayName 'PostgreSQL*' -ErrorAction SilentlyContinue
if ($kurallar) {
    $kurallar | Remove-NetFirewallRule
    Write-Host "Guvenlik duvari kurali silindi: $(@($kurallar).Count)"
} else {
    Write-Host 'PostgreSQL guvenlik duvari kurali yok.'
}

Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType -AutoSize
