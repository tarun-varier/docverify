#!/bin/bash

# ==============================================================================
# DocVerify — Single Command Launcher Script
# Starts Security Gateway (8002), ML Model (8001), Backend (8000), & Frontend (3000)
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}       Starting DocVerify Microservices Stack       ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Store PIDs of background processes
PIDS=()

# Cleanup function on Ctrl+C (SIGINT / SIGTERM)
cleanup() {
    echo -e "\n${YELLOW}Stopping all services...${NC}"
    for PID in "${PIDS[@]}"; do
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
        fi
    done
    echo -e "${GREEN}All services stopped cleanly.${NC}"
    exit 0
}

# Trap termination signals
trap cleanup SIGINT SIGTERM

# 1. Start Security Gateway (Port 8002)
echo -e "${GREEN}[1/4] Starting Security Gateway on Port 8002...${NC}"
.venv/bin/python security/app.py > /dev/null 2>&1 &
PIDS+=($!)

# 2. Start ML Model Service (Port 8001)
echo -e "${GREEN}[2/4] Starting ML Model Service on Port 8001...${NC}"
.venv/bin/python model/app.py > /dev/null 2>&1 &
PIDS+=($!)

# 3. Start Backend Service (Port 8000)
echo -e "${GREEN}[3/4] Starting Backend API on Port 8000...${NC}"
.venv/bin/python backend/app.py > /dev/null 2>&1 &
PIDS+=($!)

# Sleep briefly to let backend services initialize
sleep 2

# 4. Start Frontend Dev Server (Port 3000)
echo -e "${GREEN}[4/4] Starting React Frontend on Port 3000...${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}  DocVerify UI: http://localhost:3000${NC}"
echo -e "${YELLOW}  Press CTRL+C anytime to stop all services.${NC}"
echo -e "${BLUE}====================================================${NC}\n"

(cd frontend && npm run dev -- --port 3000) &
PIDS+=($!)

# Wait for background processes
wait
