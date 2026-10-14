$file = 'C:\Users\Appex\Documents\Default Project\CampusPilot\backend\data\perfect_timetable.xlsx'
$form = @{file = Get-Item $file}
$response = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/timetable/upload' -Method Post -Form $form -ContentType 'multipart/form-data'
$response | ConvertTo-Json -Depth 5