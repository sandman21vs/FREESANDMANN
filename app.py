import logging

from flask import Flask

import config
from app_background import _start_balance_checker
from app_hooks import register_context_processors, register_request_hooks
from init_db import init_db
from routes_admin import register_admin_routes
from routes_lawyer import register_lawyer_routes
from routes_public import register_error_handlers, register_public_routes

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


app = Flask(__name__)
app.secret_key = config.SECRET_KEY

init_db()

register_request_hooks(app)
register_context_processors(app)
register_public_routes(app)
register_admin_routes(app)
register_lawyer_routes(app)
register_error_handlers(app)


if __name__ == "__main__":
    _start_balance_checker()
    app.run(debug=True, host="0.0.0.0", port=8000)
