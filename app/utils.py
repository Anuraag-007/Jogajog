import os
import uuid
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_image(file, subfolder='vendors', max_size=(800, 800)):
    if not file or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    img = Image.open(file)
    img.thumbnail(max_size, Image.LANCZOS)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.save(filepath, optimize=True, quality=85)

    return f'uploads/{subfolder}/{filename}'


def delete_image(file_path):
    if file_path:
        full_path = os.path.join(current_app.static_folder, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)


def create_notification(user_id, ntype, title, message, link=None):
    from app.models import Notification
    from app import db
    notif = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        link=link
    )
    db.session.add(notif)
