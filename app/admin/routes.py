from functools import wraps
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.models import User, VendorProfile, Category, Booking, Enquiry, Advertisement, Review
from app import db


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'users': User.query.count(),
        'vendors': VendorProfile.query.count(),
        'active_vendors': VendorProfile.query.filter_by(is_active=True).count(),
        'verified_vendors': VendorProfile.query.filter_by(is_verified=True).count(),
        'bookings': Booking.query.count(),
        'enquiries': Enquiry.query.count(),
        'categories': Category.query.count(),
    }
    recent_vendors = VendorProfile.query.order_by(
        VendorProfile.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats,
                           recent_vendors=recent_vendors, recent_users=recent_users)


@admin_bp.route('/vendors')
@login_required
@admin_required
def vendors():
    page = request.args.get('page', 1, type=int)
    vendors_pag = VendorProfile.query.order_by(
        VendorProfile.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/vendors.html', vendors=vendors_pag)


@admin_bp.route('/vendor/<int:vendor_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_vendor(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    vendor.is_verified = not vendor.is_verified
    db.session.commit()
    status = 'verified' if vendor.is_verified else 'unverified'
    flash(f'{vendor.business_name} has been {status}.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/vendor/<int:vendor_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_vendor(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    vendor.is_active = not vendor.is_active
    db.session.commit()
    status = 'activated' if vendor.is_active else 'deactivated'
    flash(f'{vendor.business_name} has been {status}.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/make-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'admin'
    db.session.commit()
    flash(f'{user.name} is now an admin.', 'success')
    return redirect(url_for('admin.dashboard'))
