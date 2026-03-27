preload_app = True
workers = 2
bind = "0.0.0.0:8000"
timeout = 120
loglevel = "info"


def when_ready(server):
    from app import _start_balance_checker

    server.log.info("Starting background maintenance loop from Gunicorn master")
    _start_balance_checker()
