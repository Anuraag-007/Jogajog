from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='user')  # user, vendor, admin
    city = db.Column(db.String(100))
    avatar = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor_profile = db.relationship('VendorProfile', backref='owner', uselist=False)
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def unread_notification_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.phone}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(10))
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)

    vendors = db.relationship('VendorProfile', backref='category', lazy='dynamic')

    @property
    def vendor_count(self):
        return self.vendors.filter_by(is_active=True).count()


class VendorProfile(db.Model):
    __tablename__ = 'vendor_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    business_name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    description = db.Column(db.Text)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    phone = db.Column(db.String(15))
    email = db.Column(db.String(120))
    alt_phone = db.Column(db.String(15))
    price_range = db.Column(db.String(100))
    timings = db.Column(db.String(200))
    service_areas = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    listing_tier = db.Column(db.String(20), default='free')  # free, pro, featured
    accept_bookings = db.Column(db.Boolean, default=False)
    enable_chat = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(500))
    avg_rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = db.relationship('ListingImage', backref='vendor', lazy='dynamic',
                             cascade='all, delete-orphan')
    services = db.relationship('Service', backref='vendor', lazy='dynamic',
                               cascade='all, delete-orphan')
    enquiries = db.relationship('Enquiry', backref='vendor', lazy='dynamic')
    reviews = db.relationship('Review', backref='vendor', lazy='dynamic')
    bookings = db.relationship('Booking', backref='vendor', lazy='dynamic')
    chat_rooms = db.relationship('ChatRoom', backref='vendor', lazy='dynamic')
    ads = db.relationship('Advertisement', backref='vendor', lazy='dynamic')

    def update_rating(self):
        all_reviews = Review.query.filter_by(vendor_id=self.id).all()
        if all_reviews:
            self.avg_rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)
            self.review_count = len(all_reviews)
        else:
            self.avg_rating = 0.0
            self.review_count = 0

    @property
    def star_display(self):
        filled = int(round(self.avg_rating))
        return '★' * filled + '☆' * (5 - filled)

    @property
    def primary_image(self):
        img = self.images.filter_by(is_primary=True).first()
        if not img:
            img = self.images.first()
        return img.file_path if img else None

    @property
    def gallery_images(self):
        return self.images.limit(6).all()

    def __repr__(self):
        return f'<Vendor {self.business_name}>'


class ListingImage(db.Model):
    __tablename__ = 'listing_images'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.String(100))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)


class Enquiry(db.Model):
    __tablename__ = 'enquiries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, replied, closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='enquiries')


class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('ChatMessage', backref='room', lazy='dynamic',
                               cascade='all, delete-orphan')
    user = db.relationship('User', backref='chat_rooms', foreign_keys=[user_id])

    def unread_count(self, for_user_id):
        return self.messages.filter_by(is_read=False).filter(
            ChatMessage.sender_id != for_user_id
        ).count()

    @property
    def last_message(self):
        return self.messages.order_by(ChatMessage.timestamp.desc()).first()


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_rooms.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', backref='sent_messages', foreign_keys=[sender_id])


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.String(20))
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='bookings')
    service = db.relationship('Service', backref='bookings')

    STATUS_COLORS = {
        'pending': '#f5c518',
        'confirmed': '#29aee6',
        'completed': '#22c55e',
        'cancelled': '#ef4444',
    }

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, '#8490a2')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='reviews')

    @property
    def stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50))  # enquiry, booking, chat, review, system
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    TYPE_ICONS = {
        'enquiry': '📩',
        'booking': '📅',
        'chat': '💬',
        'review': '⭐',
        'system': '🔔',
    }

    @property
    def icon(self):
        return self.TYPE_ICONS.get(self.type, '🔔')


class Advertisement(db.Model):
    __tablename__ = 'advertisements'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor_profiles.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(200))
    icon = db.Column(db.String(10))
    badge_text = db.Column(db.String(50))
    placement = db.Column(db.String(50), default='banner')  # banner, featured, top
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    gradient_class = db.Column(db.String(20), default='ad-a')
    is_active = db.Column(db.Boolean, default=True)
    click_count = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
