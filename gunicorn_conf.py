import os

# Basic config
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "5010")
bind = f"{host}:{port}"

# Gunicorn config
worker_class = "uvicorn.workers.UvicornWorker"
workers = 1  # Single worker for simplicity
keepalive = 120
errorlog = "-"  # stderr
accesslog = "-"  # stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

def worker_int(worker):
    """Set worker ID in environment."""
    worker.worker_id = worker.age
    os.environ["WORKER_ID"] = str(worker.worker_id)

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    worker_int(worker) 