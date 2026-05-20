from datetime import date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.bookings import bookings_bp
from app.models import Booking, VendorProfile, Service
from app import db
from app.utils import create_notification


@bookings_bp.route('/')
@login_required
def list_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(
        Booking.created_at.desc()).all()
    return render_template('bookings/list.html', bookings=bookings)


@bookings_bp.route('/create', methods=['POST'])
@login_required
def create():
    vendor_id = request.form.get('vendor_id', type=int)
    service_id = request.form.get('service_id', type=int) or None
    booking_date_str = request.form.get('booking_date', '').strip()
    booking_time = request.form.get('booking_time', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    vendor = VendorProfile.query.get_or_404(vendor_id)
    if not vendor.accept_bookings:
        flash('This vendor does not accept bookings.', 'info')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))

    try:
        booking_date = date.fromisoformat(booking_date_str)
    except (ValueError, TypeError):
        flash('Please select a valid booking date.', 'error')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))

    if booking_date < date.today():
        flash('Booking date cannot be in the past.', 'error')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))

    booking = Booking(
        user_id=current_user.id,
        vendor_id=vendor_id,
        service_id=service_id,
        booking_date=booking_date,
        booking_time=booking_time,
        notes=notes,
    )
    db.session.add(booking)

    create_notification(
        vendor.owner.id, 'booking',
        'New Booking Request',
        f'{current_user.name} booked for {booking_date.strftime("%d %b %Y")}.',
        link='/vendor/dashboard'
    )
    db.session.commit()
    flash(f'✅ Booking request sent to {vendor.business_name}!', 'success')
    return redirect(url_for('bookings.list_bookings'))


@bookings_bp.route('/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('bookings.list_bookings'))
    if booking.status in ('completed', 'cancelled'):
        flash('Cannot cancel this booking.', 'info')
        return redirect(url_for('bookings.list_bookings'))
    booking.status = 'cancelled'
    create_notification(
        booking.vendor.owner.id, 'booking',
        'Booking Cancelled',
        f'{current_user.name} cancelled their booking.',
        link='/vendor/dashboard'
    )
    db.session.commit()
    flash('Booking cancelled.', 'info')
    return redirect(url_for('bookings.list_bookings'))
