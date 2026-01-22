@echo off
echo 🚀 Starting E-commerce Chatbot System...
echo.

echo Step 1: Starting Backend Server...
start cmd /k "cd backend && python app.py"
timeout /t 5

echo.
echo Step 2: Starting Frontend Server...
start cmd /k "cd frontend && npm run dev"
timeout /t 5

echo.
echo ✅ System is starting up!
echo.
echo 🔗 Backend: http://localhost:8000
echo 🔗 Frontend: http://localhost:5173
echo.
echo 📝 Test the system by:
echo 1. Opening http://localhost:5173 in your browser
echo 2. Typing "blue denim jacket" in the chat
echo.
pause