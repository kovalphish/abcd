from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import base64
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Default image in base64 format
DEFAULT_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

db = SQLAlchemy(app)

# Модели
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    image = db.Column(db.Text, default='default.png')  # base64 encoded image

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(20))
    customer_address = db.Column(db.String(300))
    total = db.Column(db.Float)
    status = db.Column(db.String(50), default='new')
    date = db.Column(db.DateTime, default=datetime.utcnow)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    product_name = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Создание БД
with app.app_context():
    db.create_all()

# Клиентская часть
@app.route('/')
def index():
    products = Product.query.limit(8).all()
    return render_template('index.html', products=products)

@app.route('/products')
def products():
    category = request.args.get('category')
    search = request.args.get('search')
    
    query = Product.query
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(Product.name.contains(search))
    
    products = query.all()
    categories = db.session.query(Product.category).distinct().all()
    
    return render_template('products.html', products=products, categories=categories, search=search)

@app.route('/product/<int:pid>')
def product_detail(pid):
    product = Product.query.get_or_404(pid)
    return render_template('product_detali.html', product=product)

@app.route('/cart')
def cart():
    cart_items = session.get('cart', {})
    items = []
    total = 0
    for pid, qty in cart_items.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = product.price * qty
            total += subtotal
            items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
    return render_template('cart.html', items=items, total=total)

@app.route('/add_to_cart/<int:pid>')
def add_to_cart(pid):
    cart = session.get('cart', {})
    cart[str(pid)] = cart.get(str(pid), 0) + 1
    session['cart'] = cart
    flash('Товар добавлен в корзину', 'success')
    return redirect(request.referrer or url_for('products'))

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    for pid, qty in request.form.items():
        if pid.startswith('qty_'):
            product_id = pid.split('_')[1]
            qty = int(qty)
            if qty > 0:
                cart[product_id] = qty
            elif product_id in cart:
                del cart[product_id]
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:pid>')
def remove_from_cart(pid):
    cart = session.get('cart', {})
    if str(pid) in cart:
        del cart[str(pid)]
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        cart_items = session.get('cart', {})
        if not cart_items:
            flash('Корзина пуста', 'error')
            return redirect(url_for('cart'))
        
        total = 0
        items = []
        for pid, qty in cart_items.items():
            product = Product.query.get(int(pid))
            if product and product.stock >= qty:
                subtotal = product.price * qty
                total += subtotal
                items.append({
                    'product_id': product.id,
                    'name': product.name,
                    'quantity': qty,
                    'price': product.price
                })
                product.stock -= qty
            else:
                flash(f'Товар "{product.name}" недоступен в нужном количестве', 'error')
                return redirect(url_for('cart'))
        
        order = Order(
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            total=total,
            status='new'
        )
        db.session.add(order)
        db.session.flush()
        
        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['product_id'],
                product_name=item['name'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
        
        db.session.commit()
        session['cart'] = {}
        
        flash(f'Заказ #{order.id} успешно оформлен!', 'success')
        return redirect(url_for('index'))
    
    return render_template('checkout.html')

# Админка с паролем
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash('Неверный пароль', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin():
    products = Product.query.all()
    orders = Order.query.order_by(Order.date.desc()).all()
    return render_template('admin.html', products=products, orders=orders)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@login_required
def admin_product_add():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock', 0))
        description = request.form.get('description')
        
        image = request.files.get('image')
        image_data = DEFAULT_IMAGE
        
        print(f"DEBUG: image = {image}")
        if image:
            print(f"DEBUG: image.filename = {image.filename}")
            print(f"DEBUG: allowed_file = {allowed_file(image.filename)}")
        
        if image and allowed_file(image.filename):
            # Читаем файл и конвертируем в base64
            image_bytes = image.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            # Определяем MIME тип
            ext = image.filename.rsplit('.', 1)[1].lower()
            mime_type = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'
            image_data = f"data:{mime_type};base64,{image_base64}"
            print(f"DEBUG: Изображение конвертировано в base64")
        
        product = Product(
            name=name,
            category=category,
            price=price,
            stock=stock,
            description=description,
            image=image_data
        )
        db.session.add(product)
        db.session.commit()
        flash('Товар добавлен', 'success')
        return redirect(url_for('admin'))
    
    return render_template('product_form.html', title='Добавить товар', product=None)

@app.route('/admin/product/edit/<int:pid>', methods=['GET', 'POST'])
@login_required
def admin_product_edit(pid):
    product = Product.query.get_or_404(pid)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.price = float(request.form.get('price'))
        product.stock = int(request.form.get('stock', 0))
        product.description = request.form.get('description')
        
        image = request.files.get('image')
        if image and allowed_file(image.filename):
            # Читаем файл и конвертируем в base64
            image_bytes = image.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            # Определяем MIME тип
            ext = image.filename.rsplit('.', 1)[1].lower()
            mime_type = f"image/{ext}" if ext != 'jpg' else 'image/jpeg'
            image_data = f"data:{mime_type};base64,{image_base64}"
            product.image = image_data
        
        db.session.commit()
        flash('Товар обновлен', 'success')
        return redirect(url_for('admin'))
    
    return render_template('product_form.html', title='Редактировать товар', product=product)

@app.route('/admin/product/delete/<int:pid>')
@login_required
def admin_product_delete(pid):
    product = Product.query.get(pid)
    db.session.delete(product)
    db.session.commit()
    flash('Товар удален', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/order/delete/<int:oid>')
@login_required
def admin_order_delete(oid):
    order = Order.query.get(oid)
    db.session.delete(order)
    db.session.commit()
    flash('Заказ удален', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/order/status/<int:oid>', methods=['POST'])
@login_required
def admin_order_status(oid):
    order = Order.query.get(oid)
    order.status = request.form.get('status')
    db.session.commit()
    flash('Статус заказа обновлен', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)