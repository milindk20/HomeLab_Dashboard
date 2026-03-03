import os
import bcrypt
import requests
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(50), default='fa-globe')
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='General')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)

def get_setting(key, default=''):
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else default

def set_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.context_processor
def inject_settings():
    return {
        'dashboard_title': get_setting('title', 'Homelab Dashboard'),
        'wallpaper': get_setting('wallpaper', ''),
        'theme_color': get_setting('theme_color', '#3b82f6'),
        'font_family': get_setting('font_family', 'system-ui, sans-serif'),
    }

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    services = Service.query.filter_by(status='active').all()
    categories = db.session.query(Service.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('dashboard.html', services=services, categories=categories)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    services = Service.query.all()
    settings = {
        'title': get_setting('title', 'Homelab Dashboard'),
        'theme_color': get_setting('theme_color', '#3b82f6'),
        'font_family': get_setting('font_family', 'system-ui, sans-serif'),
        'wallpaper': get_setting('wallpaper', ''),
    }
    return render_template('admin.html', services=services, settings=settings)

@app.route('/admin/service/add', methods=['POST'])
def add_service():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    service = Service(
        name=request.form['name'],
        url=request.form['url'],
        icon=request.form.get('icon', 'fa-globe'),
        description=request.form.get('description', ''),
        category=request.form.get('category', 'General'),
        status=request.form.get('status', 'active')
    )
    db.session.add(service)
    db.session.commit()
    flash('Service added successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/service/edit/<int:id>', methods=['POST'])
def edit_service(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    service = Service.query.get_or_404(id)
    service.name = request.form['name']
    service.url = request.form['url']
    service.icon = request.form.get('icon', 'fa-globe')
    service.description = request.form.get('description', '')
    service.category = request.form.get('category', 'General')
    service.status = request.form.get('status', 'active')
    db.session.commit()
    flash('Service updated successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/service/delete/<int:id>')
def delete_service(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    service = Service.query.get_or_404(id)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    set_setting('title', request.form.get('title', 'Homelab Dashboard'))
    set_setting('theme_color', request.form.get('theme_color', '#3b82f6'))
    set_setting('font_family', request.form.get('font_family', 'system-ui, sans-serif'))
    flash('Settings updated successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/wallpaper', methods=['POST'])
def upload_wallpaper():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if 'wallpaper' in request.files:
        file = request.files['wallpaper']
        if file and allowed_file(file.filename):
            filename = secure_filename(f'wallpaper_{datetime.now().timestamp()}.{file.filename.rsplit(".", 1)[1].lower()}')
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            set_setting('wallpaper', f'/static/uploads/{filename}')
            flash('Wallpaper uploaded successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/wallpaper/remove')
def remove_wallpaper():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    wallpaper = get_setting('wallpaper')
    if wallpaper:
        try:
            os.remove(os.path.join('data/Homelab_Dashboard', wallpaper.lstrip('/')))
        except:
            pass
        set_setting('wallpaper', '')
    flash('Wallpaper removed', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    user = User.query.get(session['user_id'])
    
    if not bcrypt.checkpw(current_password.encode('utf-8'), user.password_hash.encode('utf-8')):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('admin'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('admin'))
    
    user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()
    flash('Password changed successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/service-status')
def service_status():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    services = Service.query.filter_by(status='active').all()
    results = []
    
    for service in services:
        status_info = check_service_status(service.url)
        results.append({
            'id': service.id,
            'name': service.name,
            'url': service.url,
            'online': status_info['online'],
            'response_time': status_info['response_time']
        })
    
    return jsonify(results)

@app.route('/api/service-status/<int:service_id>')
def single_service_status(service_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    service = Service.query.get_or_404(service_id)
    status_info = check_service_status(service.url)
    
    return jsonify({
        'id': service.id,
        'name': service.name,
        'url': service.url,
        'online': status_info['online'],
        'response_time': status_info['response_time']
    })

def check_service_status(url):
    try:
        start_time = time.time()
        response = requests.get(url, timeout=5, verify=False, allow_redirects=True)
        response_time = int((time.time() - start_time) * 1000)
        
        if response.status_code < 500:
            return {'online': True, 'response_time': response_time}
        else:
            return {'online': False, 'response_time': response_time}
    except requests.exceptions.SSLError:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=5, verify=False, allow_redirects=True)
            response_time = int((time.time() - start_time) * 1000)
            return {'online': True, 'response_time': response_time}
        except:
            return {'online': False, 'response_time': 0}
    except:
        return {'online': False, 'response_time': 0}

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            hashed = bcrypt.hashpw('homelab'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user = User(username='admin', password_hash=hashed)
            db.session.add(user)
            db.session.commit()
            print("Default user created: admin / homelab")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
