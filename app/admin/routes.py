from functools import wraps
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.models import User, VendorProfile, Category, Booking, Enquiry, Advertisement, Review
from app import db


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash('Super admin access required.', 'error')
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
    recent_vendors = VendorProfile.query.order_by(VendorProfile.created_at.desc()).limit(10).all()
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


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    users_pag = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', users=users_pag)


@admin_bp.route('/vendor/<int:vendor_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_vendor(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    vendor.is_verified = not vendor.is_verified
    db.session.commit()
    flash(f'{vendor.business_name} {"verified" if vendor.is_verified else "unverified"}.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/vendor/<int:vendor_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_vendor(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    vendor.is_active = not vendor.is_active
    db.session.commit()
    flash(f'{vendor.business_name} {"activated" if vendor.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/vendor/<int:vendor_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_vendor(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    name = vendor.business_name
    db.session.delete(vendor)
    db.session.commit()
    flash(f'Vendor "{name}" permanently deleted.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))
    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{name}" permanently deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/user/<int:user_id>/set-role', methods=['POST'])
@login_required
@super_admin_required
def set_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('admin.users'))
    role = request.form.get('role', 'user')
    if role not in ('user', 'vendor', 'admin', 'super_admin'):
        flash('Invalid role.', 'error')
        return redirect(url_for('admin.users'))
    user.role = role
    db.session.commit()
    flash(f'{user.name} role set to {role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/make-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'admin'
    db.session.commit()
    flash(f'{user.name} is now an admin.', 'success')
    return redirect(url_for('admin.dashboard'))
