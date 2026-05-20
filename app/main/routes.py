from flask import render_template, request, jsonify
from flask_login import current_user
from sqlalchemy import or_
from app.main import main_bp
from app.models import Category, VendorProfile, Advertisement


@main_bp.route('/')
def index():
    categories = Category.query.order_by(Category.name).all()
    featured_vendors = VendorProfile.query.filter_by(
        is_active=True, is_verified=True
    ).order_by(VendorProfile.avg_rating.desc()).limit(8).all()
    ads = Advertisement.query.filter_by(is_active=True, placement='banner').all()
    city = request.args.get('city', '')
    return render_template('index.html',
                           categories=categories,
                           featured_vendors=featured_vendors,
                           ads=ads,
                           city=city)


@main_bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '')
    city = request.args.get('city', '')
    sort = request.args.get('sort', 'rating')
    filter_verified = request.args.get('verified', '')
    min_rating = request.args.get('min_rating', '')

    query = VendorProfile.query.filter_by(is_active=True)

    if q:
        term = f'%{q}%'
        query = query.filter(or_(
            VendorProfile.business_name.ilike(term),
            VendorProfile.description.ilike(term),
            VendorProfile.service_areas.ilike(term),
            VendorProfile.address.ilike(term),
        ))

    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)

    if city:
        term = f'%{city}%'
        query = query.filter(or_(
            VendorProfile.city.ilike(term),
            VendorProfile.service_areas.ilike(term),
            VendorProfile.address.ilike(term),
        ))

    if filter_verified:
        query = query.filter_by(is_verified=True)

    if min_rating:
        try:
            query = query.filter(VendorProfile.avg_rating >= float(min_rating))
        except ValueError:
            pass

    if sort == 'rating':
        query = query.order_by(VendorProfile.avg_rating.desc())
    elif sort == 'reviews':
        query = query.order_by(VendorProfile.review_count.desc())
    elif sort == 'newest':
        query = query.order_by(VendorProfile.created_at.desc())

    vendors = query.all()
    categories = Category.query.order_by(Category.name).all()

    return render_template('search.html',
                           vendors=vendors,
                           query=q,
                           city=city,
                           categories=categories,
                           category_slug=category_slug,
                           sort=sort,
                           total=len(vendors))


@main_bp.route('/vendors')
def all_vendors():
    categories = Category.query.order_by(Category.name).all()
    page = request.args.get('page', 1, type=int)
    cat_slug = request.args.get('category', '')
    filter_pill = request.args.get('filter', 'all')
    search_q = request.args.get('q', '').strip()

    query = VendorProfile.query.filter_by(is_active=True)

    if search_q:
        term = f'%{search_q}%'
        query = query.filter(or_(
            VendorProfile.business_name.ilike(term),
            VendorProfile.description.ilike(term),
        ))

    if cat_slug:
        cat = Category.query.filter_by(slug=cat_slug).first()
        if cat:
            query = query.filter_by(category_id=cat.id)

    if filter_pill == 'verified':
        query = query.filter_by(is_verified=True)
    elif filter_pill == 'rating':
        query = query.filter(VendorProfile.avg_rating >= 4.5)

    vendors_pag = query.order_by(
        VendorProfile.listing_tier.desc(),
        VendorProfile.avg_rating.desc()
    ).paginate(page=page, per_page=24, error_out=False)

    return render_template('vendors.html',
                           vendors=vendors_pag,
                           categories=categories,
                           filter_pill=filter_pill,
                           cat_slug=cat_slug,
                           search_q=search_q)


@main_bp.route('/category/<slug>')
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'rating')

    query = VendorProfile.query.filter_by(category_id=cat.id, is_active=True)
    if sort == 'rating':
        query = query.order_by(VendorProfile.avg_rating.desc())
    elif sort == 'reviews':
        query = query.order_by(VendorProfile.review_count.desc())
    elif sort == 'newest':
        query = query.order_by(VendorProfile.created_at.desc())

    vendors = query.paginate(page=page, per_page=20, error_out=False)
    categories = Category.query.order_by(Category.name).all()

    return render_template('category.html',
                           category=cat,
                           vendors=vendors,
                           categories=categories,
                           sort=sort)


@main_bp.route('/api/search-suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    term = f'%{q}%'
    vendors = VendorProfile.query.filter(
        VendorProfile.business_name.ilike(term),
        VendorProfile.is_active == True
    ).limit(6).all()
    cats = Category.query.filter(Category.name.ilike(term)).limit(4).all()
    results = []
    for v in vendors:
        results.append({
            'type': 'vendor', 'id': v.id,
            'name': v.business_name,
            'category': v.category.name if v.category else '',
            'url': f'/vendor/{v.id}'
        })
    for c in cats:
        results.append({
            'type': 'category', 'slug': c.slug,
            'name': c.name, 'icon': c.icon,
            'url': f'/category/{c.slug}'
        })
    return jsonify(results)


@main_bp.route('/api/vendors-map')
def vendors_map():
    vendors = VendorProfile.query.filter(
        VendorProfile.is_active == True,
        VendorProfile.lat.isnot(None),
        VendorProfile.lng.isnot(None)
    ).all()
    data = [{
        'id': v.id,
        'name': v.business_name,
        'lat': v.lat,
        'lng': v.lng,
        'category': v.category.name if v.category else '',
        'icon': v.category.icon if v.category else '📍',
        'rating': v.avg_rating,
        'url': f'/vendor/{v.id}'
    } for v in vendors]
    return jsonify(data)
