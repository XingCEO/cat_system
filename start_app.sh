#!/bin/bash

# Kill any existing processes on ports 8000 and 5173
echo "Cleaning up ports..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

echo "Starting Backend..."
cd backend

# Check for venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
    # Always install to ensure new deps are picked up
    echo "Updating dependencies..."
    pip install -r requirements.txt
fi

# Ensure all dependencies are definitely installed (fast check if already installed)
# pip install -r requirements.txt > /dev/null 2>&1

uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting Frontend..."
cd frontend
# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

echo "Services started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
