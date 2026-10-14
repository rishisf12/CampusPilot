$loginResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8001/auth/login" -Method Post -ContentType "application/x-www-form-urlencoded" -Body "username=metest&password=metest123"
$token = $loginResponse.access_token

$file = "C:\Users\Appex\Documents\Default Project\CampusPilot\backend\data\perfect_timetable.xlsx"
$form = @{
    file = Get-Item $file
}
$headers = @{
    Authorization = "Bearer $token"
}
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8001/timetable/upload" -Method Post -Headers $headers -Form $form -ContentType "multipart/form-data"

$response | ConvertTo-Json -Depth 5