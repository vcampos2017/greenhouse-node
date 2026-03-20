#!/bin/bash

echo "🧹 CLEAN RESTART: Greenhouse Node"

# Step 1: Kill anything running main.py (your app)
echo "🔍 Stopping any running greenhouse app..."
pkill -f main.py

# Step 2: Kill anything still using port 5000 (backup safety)
PID=$(lsof -ti :5000)

if [ -n "$PID" ]; then
    echo "⚠️ Port 5000 still in use by: $PID"
    echo "🛑 Force stopping..."
    kill -9 $PID
fi

sleep 1

# Step 3: Move to project directory
cd ~/projects/greenhouse-node || exit

# Step 4: Activate environment
echo "🐍 Activating virtual environment..."
source greenhouse-env/bin/activate

# Step 5: Start fresh instance
echo "🚀 Starting main.py..."
python main.py