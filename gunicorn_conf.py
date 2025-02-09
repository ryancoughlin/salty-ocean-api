import multiprocessing
import os

# Gunicorn config variables
workers_per_core_str = os.getenv("WORKERS_PER_CORE", "1")
web_concurrency_str = os.getenv("WEB_CONCURRENCY", None)
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "5010")
bind_env = os.getenv("BIND", None)

if bind_env:
    bind = bind_env
else:
    bind = f"{host}:{port}"

workers_per_core = float(workers_per_core_str)
cores = multiprocessing.cpu_count()
default_web_concurrency = workers_per_core * cores

if web_concurrency_str:
    web_concurrency = int(web_concurrency_str)
else:
    web_concurrency = max(int(default_web_concurrency), 2)

# Gunicorn config
worker_class = "uvicorn.workers.UvicornWorker"
workers = web_concurrency
bind = bind
keepalive = 120
errorlog = "-"  # stderr
accesslog = "-"  # stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"' 