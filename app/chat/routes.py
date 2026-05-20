from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from app.chat import chat_bp
from app.models import ChatRoom, ChatMessage, VendorProfile
from app import db, socketio
from app.utils import create_notification
from datetime import datetime


@chat_bp.route('/')
@login_required
def inbox():
    if current_user.role == 'vendor' and current_user.vendor_profile:
        rooms = current_user.vendor_profile.chat_rooms.order_by(
            ChatRoom.last_message_at.desc()).all()
    else:
        rooms = ChatRoom.query.filter_by(user_id=current_user.id).order_by(
            ChatRoom.last_message_at.desc()).all()
    return render_template('chat/inbox.html', rooms=rooms)


@chat_bp.route('/start/<int:vendor_id>')
@login_required
def start(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    if not vendor.enable_chat:
        flash('This vendor has not enabled chat.', 'info')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))
    if current_user.id == vendor.owner.id:
        flash('You cannot chat with yourself.', 'info')
        return redirect(url_for('vendor.dashboard'))

    room = ChatRoom.query.filter_by(
        user_id=current_user.id, vendor_id=vendor_id).first()
    if not room:
        room = ChatRoom(user_id=current_user.id, vendor_id=vendor_id)
        db.session.add(room)
        db.session.commit()
    return redirect(url_for('chat.room', room_id=room.id))


@chat_bp.route('/room/<int:room_id>')
@login_required
def room(room_id):
    chat_room = ChatRoom.query.get_or_404(room_id)
    vendor_owner_id = chat_room.vendor.owner.id
    if current_user.id not in (chat_room.user_id, vendor_owner_id):
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    # Mark messages as read
    ChatMessage.query.filter_by(room_id=room_id, is_read=False).filter(
        ChatMessage.sender_id != current_user.id
    ).update({'is_read': True})
    db.session.commit()

    messages = chat_room.messages.order_by(ChatMessage.timestamp.asc()).all()
    return render_template('chat/room.html', room=chat_room, messages=messages)


# SocketIO events
@socketio.on('join')
def on_join(data):
    room_id = str(data.get('room_id'))
    join_room(room_id)


@socketio.on('send_message')
def handle_message(data):
    from flask_login import current_user as cu
    if not cu.is_authenticated:
        return
    room_id = data.get('room_id')
    text = (data.get('message') or '').strip()
    if not text or not room_id:
        return
    chat_room = ChatRoom.query.get(room_id)
    if not chat_room:
        return
    vendor_owner_id = chat_room.vendor.owner.id
    if cu.id not in (chat_room.user_id, vendor_owner_id):
        return

    msg = ChatMessage(room_id=room_id, sender_id=cu.id,
                      message=text, timestamp=datetime.utcnow())
    db.session.add(msg)
    chat_room.last_message_at = datetime.utcnow()

    # Notify other party
    notify_user_id = chat_room.user_id if cu.id == vendor_owner_id else vendor_owner_id
    create_notification(
        notify_user_id, 'chat',
        'New Message',
        f'{cu.name}: {text[:60]}',
        link=f'/chat/room/{room_id}'
    )
    db.session.commit()

    emit('receive_message', {
        'id': msg.id,
        'message': msg.message,
        'sender_id': cu.id,
        'sender_name': cu.name,
        'timestamp': msg.timestamp.strftime('%I:%M %p'),
        'is_mine': True,
    }, room=str(room_id))


@socketio.on('leave')
def on_leave(data):
    room_id = str(data.get('room_id'))
    leave_room(room_id)
