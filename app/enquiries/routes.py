from flask import request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.enquiries import enquiries_bp
from app.models import Enquiry, VendorProfile
from app import db
from app.utils import create_notification


@enquiries_bp.route('/send', methods=['POST'])
def send():
    vendor_id = request.form.get('vendor_id', type=int)
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    message = request.form.get('message', '').strip()

    if not all([vendor_id, name, phone, message]):
        flash('Please fill all enquiry fields.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    vendor = VendorProfile.query.get_or_404(vendor_id)

    enquiry = Enquiry(
        vendor_id=vendor_id,
        name=name,
        phone=phone,
        message=message,
        user_id=current_user.id if current_user.is_authenticated else None
    )
    db.session.add(enquiry)

    create_notification(
        vendor.owner.id, 'enquiry',
        'New Enquiry',
        f'{name} sent an enquiry: "{message[:60]}..."',
        link=f'/vendor/dashboard'
    )
    db.session.commit()
    flash(f'✅ Enquiry sent to {vendor.business_name}! They will contact you soon.', 'success')
    return redirect(url_for('vendor.profile', vendor_id=vendor_id))
