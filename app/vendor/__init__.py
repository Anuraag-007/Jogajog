from flask import Blueprint

vendor_bp = Blueprint('vendor', __name__)

from app.vendor import routes  # noqa: F401, E402
