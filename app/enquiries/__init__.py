from flask import Blueprint

enquiries_bp = Blueprint('enquiries', __name__)

from app.enquiries import routes  # noqa: F401, E402
