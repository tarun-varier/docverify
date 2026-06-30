#!/bin/bash

# ==============================================================================
# DocVerify — Single Command Launcher Script
# Starts Security Gateway (8002), ML Model (8001), Backend (8000), & Frontend (3000)
# ==============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}       Starting DocVerify Microservices Stack       ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Pre-flight check: Check if required ports are already in use
PORTS=(3000 8000 8001 8002)
CONFLICTS=()

for PORT in "${PORTS[@]}"; do
    PID=$(lsof -t -i :"$PORT" 2>/dev/null | head -n 1)
    if [ -n "$PID" ]; then
        # On macOS/Linux get process name
        PROCESS_NAME=$(ps -p "$PID" -o comm= 2>/dev/null | xargs basename 2>/dev/null)
        [ -z "$PROCESS_NAME" ] && PROCESS_NAME="Unknown"
        CONFLICTS+=("Port $PORT is already in use by process: $PROCESS_NAME (PID $PID)")
    fi
done

if [ ${#CONFLICTS[@]} -ne 0 ]; then
    echo -e "${RED}Error: Cannot start DocVerify. Port conflict(s) detected:${NC}"
    for CONFLICT in "${CONFLICTS[@]}"; do
        echo -e "  - ${CONFLICT}"
    done
    echo -e "${YELLOW}Please stop the conflicting services/containers and try again.${NC}"
    echo -e "${BLUE}====================================================${NC}"
    exit 1
fi

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

# Ensure temp directory exists for log files
mkdir -p temp

# 1. Start Security Gateway (Port 8002)
echo -e "${GREEN}[1/4] Starting Security Gateway on Port 8002...${NC}"
.venv/bin/python security/main.py > temp/security.log 2>&1 &
PIDS+=($!)

# 2. Start ML Model Service (Port 8001)
echo -e "${GREEN}[2/4] Starting ML Model Service on Port 8001...${NC}"
.venv/bin/python model/app.py > temp/model.log 2>&1 &
PIDS+=($!)

# 3. Start Backend API on Port 8000
echo -e "${GREEN}[3/4] Starting Backend API on Port 8000...${NC}"
.venv/bin/python backend/app.py > temp/backend.log 2>&1 &
PIDS+=($!)

# Helper to check service health
wait_for_health() {
    local SERVICE_NAME=$1
    local URL=$2
    local LOG_FILE=$3
    local TARGET_PID=$4
    local MAX_ATTEMPTS=15
    local ATTEMPT=1

    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        if curl -s -f "$URL" > /dev/null; then
            echo -e "${GREEN}✓ ${SERVICE_NAME} is healthy.${NC}"
            return 0
        fi
        
        # Check if the process has died
        if ! kill -0 "$TARGET_PID" 2>/dev/null; then
            echo -e "${RED}Error: ${SERVICE_NAME} (PID ${TARGET_PID}) terminated unexpectedly.${NC}"
            if [ -f "$LOG_FILE" ]; then
                echo -e "${YELLOW}Last 15 lines of ${LOG_FILE}:${NC}"
                tail -n 15 "$LOG_FILE"
            fi
            cleanup
        fi
        
        sleep 1
        ATTEMPT=$((ATTEMPT + 1))
    done

    echo -e "${YELLOW}Warning: ${SERVICE_NAME} did not respond to health check at ${URL} within ${MAX_ATTEMPTS}s.${NC}"
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}Last 15 lines of ${LOG_FILE}:${NC}"
        tail -n 15 "$LOG_FILE"
    fi
    return 1
}

# Wait for backend microservices to initialize and be healthy
wait_for_health "Security Gateway" "http://localhost:8002/health" "temp/security.log" "${PIDS[0]}"
wait_for_health "ML Model Service" "http://localhost:8001/health" "temp/model.log" "${PIDS[1]}"
wait_for_health "Backend API" "http://localhost:8000/health" "temp/backend.log" "${PIDS[2]}"

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
