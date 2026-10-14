$body = @{
    email = "test@iiitdmj.ac.in"
    password = "test123"
    full_name = "Test User"
    programme = "BTech"
    semester = 1
    branch = "CSE A"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8001/auth/signup/start" -Method Post -ContentType "application/json" -Body $body