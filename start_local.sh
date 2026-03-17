#!/bin/bash

echo "=================================================="
echo "🏏 Starting Cricket Auction Platform Locally 🏏"
echo "=================================================="
echo ""

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Clean up port 8000 if it's already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Port 8000 is already in use. Killing the old process..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 1
fi

# Start the FastAPI backend
echo "[1/2] Starting FastAPI Backend on port 8000..."
uvicorn api_server:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait a second for backend to spin up
sleep 2

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null
then
   echo "✅ Backend is running!"
else
   echo "❌ Backend failed to start. Check for errors."
   exit 1
fi

echo ""
echo "[2/2] Launching Flutter Web Frontend in Chrome..."
cd flutter_frontend

# Run flutter in chrome
flutter run -d chrome

echo ""
echo "Shutting down..."
# When flutter exits (user presses 'q'), kill the backend
kill $BACKEND_PID
wait $BACKEND_PID 2>/dev/null
echo "Done."
