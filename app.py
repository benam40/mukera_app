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

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        if name and email:
            customer = Customer(name=name, email=email, phone=phone)
            db.session.add(customer)
            db.session.commit()
        return redirect(url_for('home'))
    customers = Customer.query.all()
    return render_template_string(
        '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Mukera CRM App</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f4f6f8; }
                .container { background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 6px #ccc; max-width: 600px; margin: auto; }
                h1 { color: #2c3e50; }
                table { width: 100%; border-collapse: collapse; margin-top: 2em; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background: #f0f0f0; }
                form { margin-top: 2em; }
                .delete-btn { color: #c0392b; text-decoration: none; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Mukera CRM App</h1>
                <form method="POST">
                    <h2>Add Customer</h2>
                    <label>Name: <input type="text" name="name" required></label><br><br>
                    <label>Email: <input type="email" name="email" required></label><br><br>
                    <label>Phone: <input type="text" name="phone"></label><br><br>
                    <button type="submit">Add Customer</button>
                </form>
                <h2>Customers</h2>
                <table>
                    <tr><th>Name</th><th>Email</th><th>Phone</th><th>Delete</th></tr>
                    {% for c in customers %}
                    <tr>
                        <td>{{c.name}}</td>
                        <td>{{c.email}}</td>
                        <td>{{c.phone}}</td>
                        <td><a href="{{ url_for('delete_customer', customer_id=c.id) }}" class="delete-btn">Delete</a></td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </body>
        </html>
        ''', customers=customers
    )

@app.route('/delete/<int:customer_id>')
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('home'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
