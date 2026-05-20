import os
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.vendor import vendor_bp
from app.models import VendorProfile, Category, ListingImage, Service, Review, Booking, Enquiry, ChatRoom
from app import db
from app.utils import save_image, delete_image, create_notification


@vendor_bp.route('/<int:vendor_id>')
def profile(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    if not vendor.is_active:
        flash('This vendor profile is not available.', 'info')
        return redirect(url_for('main.index'))
    vendor.view_count = (vendor.view_count or 0) + 1
    db.session.commit()
    reviews = Review.query.filter_by(vendor_id=vendor_id).order_by(
        Review.created_at.desc()).limit(10).all()
    services = vendor.services.filter_by(is_active=True).all()
    gallery = vendor.gallery_images
    return render_template('vendor_profile.html',
                           vendor=vendor, reviews=reviews,
                           services=services, gallery=gallery)


@vendor_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.vendor_profile:
        flash('You already have a vendor profile.', 'info')
        return redirect(url_for('vendor.dashboard'))

    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        category_id = request.form.get('category_id', type=int)
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip() or None
        alt_phone = request.form.get('alt_phone', '').strip() or None
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        pincode = request.form.get('pincode', '').strip() or None
        service_areas = request.form.get('service_areas', '').strip()
        price_range = request.form.get('price_range', '').strip() or None
        timings = request.form.get('timings', '').strip() or None
        description = request.form.get('description', '').strip()
        accept_bookings = bool(request.form.get('accept_bookings'))
        enable_chat = bool(request.form.get('enable_chat'))
        apply_verified = bool(request.form.get('apply_verified'))
        lat = request.form.get('lat', type=float)
        lng = request.form.get('lng', type=float)

        if not all([business_name, category_id, phone, address, city, description]):
            flash('Please fill all required fields.', 'error')
            return render_template('vendor_register.html', categories=categories)

        vendor = VendorProfile(
            user_id=current_user.id,
            business_name=business_name,
            category_id=category_id,
            phone=phone,
            email=email,
            alt_phone=alt_phone,
            address=address,
            city=city,
            pincode=pincode,
            service_areas=service_areas,
            price_range=price_range,
            timings=timings,
            description=description,
            accept_bookings=accept_bookings,
            enable_chat=enable_chat,
            lat=lat,
            lng=lng,
        )
        db.session.add(vendor)
        db.session.flush()

        # Handle profile image upload
        profile_img = request.files.get('profile_image')
        if profile_img and profile_img.filename:
            path = save_image(profile_img, subfolder='vendors')
            if path:
                vendor.profile_image = path
                img = ListingImage(vendor_id=vendor.id, file_path=path, is_primary=True)
                db.session.add(img)

        # Handle gallery images upload
        gallery_files = request.files.getlist('gallery_images')
        for gf in gallery_files[:5]:
            if gf and gf.filename:
                path = save_image(gf, subfolder='vendors')
                if path:
                    db.session.add(ListingImage(vendor_id=vendor.id, file_path=path))

        # Handle services from form
        service_names = request.form.getlist('service_name[]')
        service_prices = request.form.getlist('service_price[]')
        for sname, sprice in zip(service_names, service_prices):
            sname = sname.strip()
            if sname:
                db.session.add(Service(vendor_id=vendor.id, name=sname,
                                       price=sprice.strip() or None))

        # Also handle tag-style services
        tag_services = request.form.get('tag_services', '')
        for tag in tag_services.split(','):
            tag = tag.strip()
            if tag:
                db.session.add(Service(vendor_id=vendor.id, name=tag))

        current_user.role = 'vendor'
        db.session.commit()

        flash('🎉 Your vendor listing is live! Welcome to the Jogajog family.', 'success')
        return redirect(url_for('vendor.dashboard'))

    return render_template('vendor_register.html', categories=categories)


@vendor_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.vendor_profile:
        flash('Please register as a vendor first.', 'info')
        return redirect(url_for('vendor.register'))
    vendor = current_user.vendor_profile
    recent_bookings = vendor.bookings.order_by(
        Booking.created_at.desc()).limit(5).all() if vendor.accept_bookings else []
    recent_enquiries = vendor.enquiries.order_by(
        Enquiry.created_at.desc()).limit(5).all()
    recent_reviews = vendor.reviews.order_by(
        Review.created_at.desc()).limit(5).all()
    recent_chats = vendor.chat_rooms.order_by(
        ChatRoom.last_message_at.desc()).limit(5).all() if vendor.enable_chat else []
    return render_template('dashboard/vendor.html',
                           vendor=vendor,
                           recent_bookings=recent_bookings,
                           recent_enquiries=recent_enquiries,
                           recent_reviews=recent_reviews,
                           recent_chats=recent_chats)


@vendor_bp.route('/dashboard/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if not current_user.vendor_profile:
        return redirect(url_for('vendor.register'))
    vendor = current_user.vendor_profile
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        vendor.business_name = request.form.get('business_name', vendor.business_name).strip()
        vendor.category_id = request.form.get('category_id', vendor.category_id, type=int)
        vendor.phone = request.form.get('phone', vendor.phone).strip()
        vendor.email = request.form.get('email', '').strip() or None
        vendor.alt_phone = request.form.get('alt_phone', '').strip() or None
        vendor.address = request.form.get('address', vendor.address).strip()
        vendor.city = request.form.get('city', vendor.city).strip()
        vendor.pincode = request.form.get('pincode', '').strip() or None
        vendor.service_areas = request.form.get('service_areas', '').strip()
        vendor.price_range = request.form.get('price_range', '').strip() or None
        vendor.timings = request.form.get('timings', '').strip() or None
        vendor.description = request.form.get('description', vendor.description).strip()
        vendor.accept_bookings = bool(request.form.get('accept_bookings'))
        vendor.enable_chat = bool(request.form.get('enable_chat'))
        lat = request.form.get('lat', type=float)
        lng = request.form.get('lng', type=float)
        if lat and lng:
            vendor.lat = lat
            vendor.lng = lng

        profile_img = request.files.get('profile_image')
        if profile_img and profile_img.filename:
            if vendor.profile_image:
                delete_image(vendor.profile_image)
            path = save_image(profile_img, subfolder='vendors')
            if path:
                vendor.profile_image = path
                old_primary = ListingImage.query.filter_by(
                    vendor_id=vendor.id, is_primary=True).first()
                if old_primary:
                    old_primary.file_path = path
                else:
                    db.session.add(ListingImage(vendor_id=vendor.id,
                                                file_path=path, is_primary=True))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('vendor.dashboard'))

    return render_template('dashboard/vendor_edit.html', vendor=vendor, categories=categories)


@vendor_bp.route('/dashboard/booking/<int:booking_id>/status', methods=['POST'])
@login_required
def update_booking_status(booking_id):
    from app.models import Booking
    booking = Booking.query.get_or_404(booking_id)
    if booking.vendor_id != current_user.vendor_profile.id:
        return jsonify({'error': 'Unauthorized'}), 403
    new_status = request.form.get('status')
    if new_status in ('confirmed', 'completed', 'cancelled'):
        booking.status = new_status
        create_notification(
            booking.user_id, 'booking',
            f'Booking {new_status.title()}',
            f'Your booking with {booking.vendor.business_name} is {new_status}.',
            link=f'/bookings'
        )
        db.session.commit()
        flash(f'Booking marked as {new_status}.', 'success')
    return redirect(url_for('vendor.dashboard'))


@vendor_bp.route('/review/<int:vendor_id>', methods=['POST'])
@login_required
def add_review(vendor_id):
    vendor = VendorProfile.query.get_or_404(vendor_id)
    existing = Review.query.filter_by(
        user_id=current_user.id, vendor_id=vendor_id).first()
    if existing:
        flash('You have already reviewed this vendor.', 'info')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    if not rating or rating < 1 or rating > 5:
        flash('Please provide a valid rating.', 'error')
        return redirect(url_for('vendor.profile', vendor_id=vendor_id))
    review = Review(user_id=current_user.id, vendor_id=vendor_id,
                    rating=rating, comment=comment)
    db.session.add(review)
    db.session.flush()
    vendor.update_rating()
    create_notification(
        vendor.owner.id, 'review',
        'New Review',
        f'{current_user.name} gave you {rating}★ review.',
        link=f'/vendor/{vendor_id}'
    )
    db.session.commit()
    flash('Thank you for your review! ⭐', 'success')
    return redirect(url_for('vendor.profile', vendor_id=vendor_id))
