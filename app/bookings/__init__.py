from flask import Blueprint

bookings_bp = Blueprint('bookings', __name__)

from app.bookings import routes  # noqa: F401, E402
