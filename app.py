from flask import Flask, render_template_string, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Lead')  # Lead, Opportunity, Customer
    notes = db.Column(db.Text, default='')

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    search = request.args.get('search', '')
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        status = request.form.get('status', 'Lead')
        notes = request.form.get('notes', '')
        if name and email:
            customer = Customer(name=name, email=email, phone=phone, status=status, notes=notes)
            db.session.add(customer)
            db.session.commit()
        return redirect(url_for('home'))
    if search:
        customers = Customer.query.filter(
            (Customer.name.ilike(f'%{search}%')) | (Customer.email.ilike(f'%{search}%'))
        ).all()
    else:
        customers = Customer.query.all()
    return render_template_string(
        '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Mukera CRM App</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container my-5">
                <h1 class="mb-4">Mukera CRM App</h1>
                <form method="GET" class="row mb-4">
                    <div class="col-auto">
                        <input type="text" class="form-control" name="search" placeholder="Search by name or email" value="{{request.args.get('search', '')}}">
                    </div>
                    <div class="col-auto">
                        <button type="submit" class="btn btn-primary">Search</button>
                        <a href="/" class="btn btn-secondary">Clear</a>
                    </div>
                </form>
                <form method="POST" class="card card-body mb-4">
                    <h2 class="h5">Add Customer</h2>
                    <div class="row g-2">
                        <div class="col-md-3"><input type="text" class="form-control" name="name" placeholder="Name" required></div>
                        <div class="col-md-3"><input type="email" class="form-control" name="email" placeholder="Email" required></div>
                        <div class="col-md-2"><input type="text" class="form-control" name="phone" placeholder="Phone"></div>
                        <div class="col-md-2">
                            <select class="form-select" name="status">
                                <option value="Lead">Lead</option>
                                <option value="Opportunity">Opportunity</option>
                                <option value="Customer">Customer</option>
                            </select>
                        </div>
                        <div class="col-md-12 mt-2">
                            <textarea class="form-control" name="notes" placeholder="Notes"></textarea>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-success mt-3">Add Customer</button>
                </form>
                <h2 class="h5 mb-3">Customers</h2>
                <table class="table table-bordered table-hover bg-white">
                    <thead class="table-light">
                        <tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Notes</th><th>Edit</th><th>Delete</th></tr>
                    </thead>
                    <tbody>
                    {% for c in customers %}
                    <tr>
                        <td>{{c.name}}</td>
                        <td>{{c.email}}</td>
                        <td>{{c.phone}}</td>
                        <td>{{c.status}}</td>
                        <td style="max-width:200px; white-space:pre-wrap;">{{c.notes}}</td>
                        <td><a href="{{ url_for('edit_customer', customer_id=c.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                        <td><a href="{{ url_for('delete_customer', customer_id=c.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        ''', customers=customers)

@app.route('/edit/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.email = request.form.get('email')
        customer.phone = request.form.get('phone')
        customer.status = request.form.get('status')
        customer.notes = request.form.get('notes')
        db.session.commit()
        return redirect(url_for('home'))
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Customer</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container my-5">
            <h1 class="mb-4">Edit Customer</h1>
            <form method="POST" class="card card-body">
                <div class="row g-2">
                    <div class="col-md-3"><input type="text" class="form-control" name="name" value="{{customer.name}}" required></div>
                    <div class="col-md-3"><input type="email" class="form-control" name="email" value="{{customer.email}}" required></div>
                    <div class="col-md-2"><input type="text" class="form-control" name="phone" value="{{customer.phone}}"></div>
                    <div class="col-md-2">
                        <select class="form-select" name="status">
                            <option value="Lead" {% if customer.status=='Lead' %}selected{% endif %}>Lead</option>
                            <option value="Opportunity" {% if customer.status=='Opportunity' %}selected{% endif %}>Opportunity</option>
                            <option value="Customer" {% if customer.status=='Customer' %}selected{% endif %}>Customer</option>
                        </select>
                    </div>
                    <div class="col-md-12 mt-2">
                        <textarea class="form-control" name="notes">{{customer.notes}}</textarea>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary mt-3">Save Changes</button>
                <a href="/" class="btn btn-secondary mt-3">Cancel</a>
            </form>
        </div>
    </body>
    </html>
    ''', customer=customer)

@app.route('/delete/<int:customer_id>')
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
