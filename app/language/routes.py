from flask import session, redirect, request, url_for
from app.language import language_bp

SUPPORTED = {'en', 'hi'}

@language_bp.route('/set/<lang>')
def set_lang(lang):
    if lang in SUPPORTED:
        session['lang'] = lang
    return redirect(request.referrer or url_for('main.index'))
