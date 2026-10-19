# Komite O-3: AIRAC yenilemesini her gün 12:00'de (kaçırılırsa ilk fırsatta) çalıştıran Windows görevi.
# Döngü bitmediyse görev DHMİ'ye istek atmadan çıkar. Kaldırmak: Unregister-ScheduledTask -TaskName "TurbulansRadar AIRAC yenileme"
$kok = Split-Path $PSScriptRoot -Parent
$komut = "~/.venvs/turbulans/bin/python -m turbulans_radar.cli.airac_yenile >> ciktilar/airac_yenile.log 2>&1"
$islem = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "--cd `"$kok`" -e bash -lc `"$komut`""
$tetik = New-ScheduledTaskTrigger -Daily -At 12:00
$ayar = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "TurbulansRadar AIRAC yenileme" -Action $islem -Trigger $tetik -Settings $ayar `
    -Description "AIP Türkiye ATS ağı ve ENR 5.1 sahalarını AIRAC bitince yeniler (src/turbulans_radar/cli/airac_yenile.py)." -Force
