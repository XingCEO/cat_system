#!/bin/bash

# Kill any existing processes on ports 8000 and 5174
echo "Cleaning up ports..."
lsof -ti:8000 | xargs -r kill -9 2>/dev/null
lsof -ti:5174 | xargs -r kill -9 2>/dev/null

echo "Starting Backend..."
cd backend

# Check for venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install/update dependencies
source venv/bin/activate
echo "Updating dependencies..."
# Verify venv activation
echo "Python interpreter: $(which python3)"
# Corrected command: use python3 -m pip
python3 -m pip install -r requirements.txt --upgrade

# Corrected command: use python3 -m uvicorn
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting Frontend..."
cd frontend
# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
# Corrected command: specify port 5174 for frontend
npm run dev -- --port 5174 &
FRONTEND_PID=$!
cd ..

echo "Services started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5174"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
