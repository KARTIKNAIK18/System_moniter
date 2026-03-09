import psutil
from fastapi import FastAPI
from app.helper.system_health import SystemMonitor


app = FastAPI()


@app.get("/metrics")
async def root():
    monitor = SystemMonitor()
    stats = monitor.get_all_stats()
    return stats   