# Start script for CashLoop
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting CashLoop Backend & Frontend" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "CashLoop Backend running on http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "CashLoop Frontend running on http://localhost:3000" -ForegroundColor Green
