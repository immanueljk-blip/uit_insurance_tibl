import os
import multiprocessing

# Bind to port 8051 for production access
bind = "0.0.0.0:8051"

# Concurrency workers configuration (default to 2 * CPUs + 1)
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Process handling and keepalive
timeout = 120
keepalive = 5

# Production server logging setup
os.makedirs("logs", exist_ok=True)
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
