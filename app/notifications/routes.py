from flask import render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.notifications import notifications_bp
from app.models import Notification
from app import db


@notifications_bp.route('/')
@login_required
def list_notifications():
    notifications = current_user.notifications.order_by(
        Notification.created_at.desc()).limit(50).all()
    # Mark all as read
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('notifications/list.html', notifications=notifications)


@notifications_bp.route('/mark-read', methods=['POST'])
@login_required
def mark_read():
    notif_id = request.form.get('id', type=int)
    if notif_id:
        notif = Notification.query.get(notif_id)
        if notif and notif.user_id == current_user.id:
            notif.is_read = True
            db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/count')
@login_required
def count():
    c = current_user.notifications.filter_by(is_read=False).count()
    return jsonify({'count': c})
