import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins='*', async_mode='eventlet')

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to continue.'
    login_manager.login_message_category = 'info'

    from app.auth import auth_bp
    from app.main import main_bp
    from app.vendor import vendor_bp
    from app.chat import chat_bp
    from app.bookings import bookings_bp
    from app.enquiries import enquiries_bp
    from app.notifications import notifications_bp
    from app.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(vendor_bp, url_prefix='/vendor')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(enquiries_bp, url_prefix='/enquiry')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'vendors'), exist_ok=True)

    with app.app_context():
        from app import models
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    from app.models import Category, Advertisement
    if Category.query.count() > 0:
        return

    categories = [
        ('⚡', 'Electrician', 'electrician'),
        ('🔧', 'Plumber', 'plumber'),
        ('❄️', 'AC Repair', 'ac-repair'),
        ('🧹', 'Cleaning', 'cleaning'),
        ('🪚', 'Carpenter', 'carpenter'),
        ('🎨', 'Painter', 'painter'),
        ('🩺', 'Doctor / Clinic', 'doctor-clinic'),
        ('🚗', 'Mechanic', 'mechanic'),
        ('💇', 'Salon & Beauty', 'salon-beauty'),
        ('📚', 'Tutor', 'tutor'),
        ('🍽️', 'Catering', 'catering'),
        ('🔒', 'Security / CCTV', 'security-cctv'),
        ('🚚', 'Movers & Packers', 'movers-packers'),
        ('📱', 'Electronics', 'electronics'),
        ('🛒', 'Grocery / Kirana', 'grocery-kirana'),
        ('🪑', 'Furniture', 'furniture'),
        ('🌿', 'Gardening', 'gardening'),
        ('🍼', 'Babysitter', 'babysitter'),
        ('🏥', 'Healthcare', 'healthcare'),
        ('🛠️', 'Other Services', 'other'),
    ]
    for icon, name, slug in categories:
        db.session.add(Category(name=name, slug=slug, icon=icon))

    ads = [
        ('⚡', 'Fast Electrician', 'Response in 30 mins', 'HOT', 'banner', 'ad-a'),
        ('🏥', 'Home Doctor Visit', 'Book Now – ₹299', 'NEW', 'banner', 'ad-c'),
        ('🎨', 'Wall Painting', 'Free estimate today', 'OFFER', 'banner', 'ad-e'),
        ('👗', 'Festive Sale', 'Up to 50% OFF', 'SALE', 'banner', 'ad-b'),
        ('🔧', 'AC Service Deal', 'Just ₹499 all-in', 'DEAL', 'banner', 'ad-d'),
        ('🍽️', 'Catering Orders', 'Min 20 persons', 'BOOK', 'banner', 'ad-f'),
        ('🛡️', 'Security Install', 'CCTV from ₹1999', 'SAVE', 'banner', 'ad-a'),
        ('🔌', 'Electronics Shop', 'Warranty guaranteed', '✓', 'banner', 'ad-c'),
    ]
    for icon, title, subtitle, badge, placement, gradient in ads:
        db.session.add(Advertisement(
            icon=icon, title=title, subtitle=subtitle,
            badge_text=badge, placement=placement, gradient_class=gradient
        ))
    db.session.commit()
