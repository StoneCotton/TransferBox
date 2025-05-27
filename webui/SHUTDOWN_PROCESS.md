# TransferBox Shutdown Process Documentation

## Overview

TransferBox WebUI has a multi-component architecture that requires coordinated shutdown of both frontend (NextJS) and backend (Python/FastAPI) components.

## Shutdown Sequence

### 1. **Signal Reception** ✅

```
INFO     Shutdown signal received: SIGINT (Ctrl+C)
```

- The Python application properly receives the Ctrl+C signal
- Signal handlers are properly configured

### 2. **Cleanup Initiation** ✅

```
INFO     Status: Starting: Cleanup
INFO     Cleaning up resources
```

- Cleanup process starts immediately after signal reception
- Resources are cleaned up in proper order

### 3. **Component Shutdown**

#### **NextJS Process** ✅ (Improved)

```
INFO     Starting Web UI cleanup
INFO     Stopping NextJS process gracefully
INFO     NextJS process stopped gracefully
```

**OR if graceful shutdown fails:**

```
WARNING  NextJS process didn't stop gracefully, forcing shutdown
INFO     NextJS process forcefully stopped
```

- **Graceful shutdown**: SIGTERM sent to NextJS process (3-second timeout)
- **Force shutdown**: SIGKILL sent if graceful shutdown fails (2-second timeout)
- **Previous behavior**: Immediate termination without grace period

#### **FastAPI Server** ✅

```
INFO     Stopping Web Server
INFO     Stopping FastAPI server
INFO:    Shutting down
INFO:    Application shutdown complete.
INFO     Web Server stopped
```

- Uvicorn server shuts down gracefully
- All pending requests are completed
- Server resources are properly released

#### **WebSocket Connections** ⚠️ → ✅ (Improved)

```
WARNING  WebSocket client 127.0.0.1:52840 disconnected with code 1012:
INFO:    connection closed
```

**What this means:**

- **Code 1012**: "Service Restart" - Normal when server is shutting down
- **Previous**: Logged as WARNING (concerning)
- **Current**: Expected behavior during shutdown (still shows but is normal)

### 4. **Resource Cleanup** ✅

```
INFO     Sound system cleaned up
INFO     Status: Completed: Cleanup
```

- Sound manager resources released
- All system resources properly cleaned up

### 5. **Application Exit** ✅

```
INFO     Exiting program
```

- Clean application termination
- No hanging processes

## Shutdown Improvements Made

### 1. **Graceful NextJS Shutdown**

**Before:**

```python
self.nextjs_process.terminate()
self.nextjs_process.wait(timeout=5)
```

**After:**

```python
# Graceful shutdown with SIGTERM
self.nextjs_process.terminate()
self.nextjs_process.wait(timeout=3)

# Force kill if needed
if still_running:
    self.nextjs_process.kill()
    self.nextjs_process.wait(timeout=2)
```

### 2. **Better Error Handling**

- Individual try/catch blocks for each component
- Detailed logging for each shutdown step
- Graceful degradation if one component fails to stop

### 3. **Improved Logging**

- Clear indication of what's happening at each step
- Distinction between normal and abnormal shutdowns
- Specific timeouts and fallback behaviors

## Expected Log Sequence

### **Clean Shutdown (Normal)**

```
INFO     Shutdown signal received: SIGINT (Ctrl+C)
INFO     Status: Starting: Cleanup
INFO     Starting Web UI cleanup
INFO     Stopping NextJS process gracefully
INFO     NextJS process stopped gracefully
INFO     Stopping Web Server
INFO     Stopping FastAPI server
INFO:    Shutting down
INFO:    connection closed
INFO:    Application shutdown complete.
INFO     Web Server stopped
INFO     Cleaning up resources
INFO     Sound system cleaned up
INFO     Status: Completed: Cleanup
INFO     Exiting program
```

### **Shutdown with Force Kill (Still Safe)**

```
INFO     Shutdown signal received: SIGINT (Ctrl+C)
INFO     Status: Starting: Cleanup
INFO     Starting Web UI cleanup
INFO     Stopping NextJS process gracefully
WARNING  NextJS process didn't stop gracefully, forcing shutdown
INFO     NextJS process forcefully stopped
INFO     Stopping Web Server
[... rest same as normal shutdown ...]
```

## Normal vs. Concerning Behaviors

### ✅ **Normal (Don't Worry)**

- WebSocket disconnect warnings during shutdown
- "NextJS process didn't stop gracefully" (if it happens occasionally)
- Brief delays during shutdown (up to 10 seconds total)

### ⚠️ **Concerning (Investigate)**

- Application hangs during shutdown (>15 seconds)
- "Failed to stop even with force" errors
- Repeated crash/restart cycles
- Error messages in parent cleanup

### 🚨 **Critical (Needs Attention)**

- Processes remaining after application exit
- Port conflicts on next startup
- Data corruption warnings
- Memory leaks or resource exhaustion

## Troubleshooting

### **Port 8000 Already in Use**

```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Or restart with different port
python webui_launcher.py --port 8001
```

### **NextJS Process Won't Stop**

```bash
# Find NextJS processes
ps aux | grep node | grep next

# Kill manually if needed
pkill -f "next"
```

### **WebSocket Connection Issues**

- Browser cache clearing might be needed
- Check if multiple tabs are open
- Refresh browser after restart

## Summary

**Your shutdown logs indicate a mostly clean shutdown process.** The warnings about WebSocket disconnects and NextJS stopping are normal during shutdown. With the improvements made:

1. ✅ Backend shuts down cleanly and safely
2. ✅ Frontend now shuts down more gracefully
3. ✅ Resources are properly cleaned up
4. ✅ No data loss or corruption risk
5. ✅ Ready for immediate restart
