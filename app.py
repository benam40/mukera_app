from flask import Flask, render_template_string, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
# import pandas as pd  # Temporarily disabled
import os
import io
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# --- SMTP Config (set these to your email provider's values) ---
SMTP_SERVER = 'smtp.example.com'
SMTP_PORT = 587
SMTP_USERNAME = 'your_username@example.com'
SMTP_PASSWORD = 'your_password'
SENDER_EMAIL = 'your_username@example.com'


app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages
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
    contacts = db.relationship('Contact', backref='customer', cascade="all, delete-orphan")
    tasks = db.relationship('Task', backref='customer', cascade="all, delete-orphan")
    deals = db.relationship('Deal', backref='customer', cascade="all, delete-orphan")
    reminders = db.relationship('Reminder', backref='customer', cascade="all, delete-orphan")

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(50))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Todo')  # Todo, In Progress, Done

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, default=0)
    stage = db.Column(db.String(50), default='New')  # New, Qualified, Won, Lost
    status = db.Column(db.String(20), default='Open')  # Open, Closed

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.String(20))
    completed = db.Column(db.Boolean, default=False)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='Call') # Call, Meeting, Task, Email
    date = db.Column(db.String(20))
    related_type = db.Column(db.String(20)) # Customer, Deal, Lead
    related_id = db.Column(db.Integer)
    notes = db.Column(db.Text, default='')

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    start_date = db.Column(db.String(20))
    end_date = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Draft')  # Draft, Active, Completed
    steps = db.relationship('CampaignStep', backref='campaign', cascade="all, delete-orphan")

class Segment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    filter_type = db.Column(db.String(20))  # e.g., 'Lead', 'Customer'
    filter_value = db.Column(db.String(100))

class CampaignStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    step_type = db.Column(db.String(20))  # Email, Wait
    details = db.Column(db.Text)  # JSON or text for email body, wait time, etc.
    order = db.Column(db.Integer, default=0)

class CampaignLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer)
    segment_id = db.Column(db.Integer)
    recipient_email = db.Column(db.String(120))
    step_id = db.Column(db.Integer)
    status = db.Column(db.String(20))  # Sent, Failed, Completed
    timestamp = db.Column(db.String(20))

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    company = db.Column(db.String(100))
    status = db.Column(db.String(20), default='New')  # New, Assigned, Converted, Lost
    notes = db.Column(db.Text, default='')

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def home():
    tab = request.args.get('tab', 'customers')
    # Always define deals_by_stage for template context
    deal_stages = ['New', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost']
    deals_by_stage = {stage: [] for stage in deal_stages}
    for d in Deal.query.all():
        deals_by_stage.get(d.stage, []).append(d)
    # Leads logic
    leads = Lead.query.all()
    # Activities logic
    activities = Activity.query.order_by(Activity.date).all()
    activities_by_date = {}
    for a in activities:
        activities_by_date.setdefault(a.date, []).append(a)
    # Marketing logic
    campaigns = Campaign.query.all()
    segments = Segment.query.all()
    selected_campaign = None
    campaign_steps = []
    selected_segment = None
    campaign_logs = []
    campaign_stats = None
    campaign_id = request.args.get('campaign_id')
    if campaign_id:
        selected_campaign = Campaign.query.get(int(campaign_id))
        campaign_steps = CampaignStep.query.filter_by(campaign_id=campaign_id).order_by(CampaignStep.order).all()
        campaign_logs = CampaignLog.query.filter_by(campaign_id=campaign_id).all()
        # Simple stats
        campaign_stats = {
            'total': len(campaign_logs),
            'sent': len([l for l in campaign_logs if l.status=='Sent']),
            'failed': len([l for l in campaign_logs if l.status=='Failed']),
            'completed': len([l for l in campaign_logs if l.status=='Completed'])
        }
    segment_id = request.args.get('segment_id')
    if segment_id:
        selected_segment = Segment.query.get(int(segment_id))
    search = request.args.get('search', '')
    customers = Customer.query
    if search:
        customers = customers.filter((Customer.name.ilike(f'%{search}%')) | (Customer.email.ilike(f'%{search}%')))
    customers = customers.all()
    # Advanced filters for each module
    contact_customer_filter = request.args.get('contact_customer', '')
    task_status_filter = request.args.get('task_status', '')
    task_due_filter = request.args.get('task_due', '')
    deal_stage_filter = request.args.get('deal_stage', '')
    deal_status_filter = request.args.get('deal_status', '')
    reminder_due_filter = request.args.get('reminder_due', '')
    reminder_completed_filter = request.args.get('reminder_completed', '')

    contacts = Contact.query
    if contact_customer_filter:
        contacts = contacts.filter(Contact.customer_id == contact_customer_filter)
    contacts = contacts.all()

    tasks = Task.query
    if task_status_filter:
        tasks = tasks.filter(Task.status == task_status_filter)
    if task_due_filter:
        tasks = tasks.filter(Task.due_date == task_due_filter)
    tasks = tasks.all()

    deals = Deal.query
    if deal_stage_filter:
        deals = deals.filter(Deal.stage == deal_stage_filter)
    if deal_status_filter:
        deals = deals.filter(Deal.status == deal_status_filter)
    deals = deals.all()

    reminders = Reminder.query
    if reminder_due_filter:
        reminders = reminders.filter(Reminder.due_date == reminder_due_filter)
    if reminder_completed_filter:
        reminders = reminders.filter(Reminder.completed == (reminder_completed_filter == 'yes'))
    reminders = reminders.all()
    msg = None
    if request.method == 'POST':
        # Add campaign
        if 'add_campaign' in request.form:
            name = request.form.get('campaign_name')
            desc = request.form.get('campaign_desc')
            start = request.form.get('campaign_start')
            end = request.form.get('campaign_end')
            status = request.form.get('campaign_status')
            camp = Campaign(name=name, description=desc, start_date=start, end_date=end, status=status)
            db.session.add(camp)
            db.session.commit()
            msg = 'Campaign added.'
        # Delete campaign
        if 'delete_campaign' in request.form:
            campaign_id = request.form.get('delete_campaign')
            camp = Campaign.query.get(campaign_id)
            db.session.delete(camp)
            db.session.commit()
            msg = 'Campaign deleted.'
        # Add segment
        if 'add_segment' in request.form:
            name = request.form.get('segment_name')
            filter_type = request.form.get('segment_filter_type')
            filter_value = request.form.get('segment_filter_value')
            seg = Segment(name=name, filter_type=filter_type, filter_value=filter_value)
            db.session.add(seg)
            db.session.commit()
            msg = 'Segment added.'
        # Delete segment
        if 'delete_segment' in request.form:
            segment_id = request.form.get('delete_segment')
            seg = Segment.query.get(segment_id)
            db.session.delete(seg)
            db.session.commit()
            msg = 'Segment deleted.'
        # Add campaign step
        if 'add_campaign_step' in request.form:
            campaign_id = request.form.get('campaign_id')
            step_type = request.form.get('step_type')
            details = request.form.get('step_details')
            order = int(request.form.get('step_order', 0))
            step = CampaignStep(campaign_id=campaign_id, step_type=step_type, details=details, order=order)
            db.session.add(step)
            db.session.commit()
            msg = 'Step added.'
        # Delete campaign step
        if 'delete_campaign_step' in request.form:
            step_id = request.form.get('delete_campaign_step')
            step = CampaignStep.query.get(step_id)
            db.session.delete(step)
            db.session.commit()
            msg = 'Step deleted.'
        # Run campaign (send email blast)
        if 'run_campaign' in request.form:
            campaign_id = request.form.get('campaign_id')
            segment_id = request.form.get('segment_id')
            segment = Segment.query.get(segment_id)
            steps = CampaignStep.query.filter_by(campaign_id=campaign_id).order_by(CampaignStep.order).all()
            # Get recipients
            if segment.filter_type == 'Lead':
                recipients = Lead.query
                if segment.filter_value:
                    recipients = recipients.filter_by(status=segment.filter_value)
                recipients = recipients.all()
            else:
                recipients = Customer.query
                if segment.filter_value:
                    recipients = recipients.filter_by(status=segment.filter_value)
                recipients = recipients.all()
            # For each recipient, process steps (only Email steps for now)
            for r in recipients:
                for step in steps:
                    if step.step_type == 'Email':
                        # details = subject|||body
                        try:
                            subj, body = step.details.split('|||', 1)
                            msg_obj = MIMEText(body)
                            msg_obj['Subject'] = subj
                            msg_obj['From'] = SENDER_EMAIL
                            msg_obj['To'] = r.email
                            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                                server.starttls()
                                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                                server.sendmail(SENDER_EMAIL, [r.email], msg_obj.as_string())
                            status = 'Sent'
                        except Exception as e:
                            status = 'Failed'
                        log = CampaignLog(campaign_id=campaign_id, segment_id=segment_id, recipient_email=r.email, step_id=step.id, status=status, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'))
                        db.session.add(log)
                        db.session.commit()
            msg = 'Campaign run complete.'
        # Send email
        if 'send_email' in request.form:
            recipient = request.form.get('recipient')
            subject = request.form.get('subject')
            body = request.form.get('body')
            date = datetime.now().strftime('%Y-%m-%d')
            try:
                msg_obj = MIMEText(body)
                msg_obj['Subject'] = subject
                msg_obj['From'] = SENDER_EMAIL
                msg_obj['To'] = recipient
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.sendmail(SENDER_EMAIL, [recipient], msg_obj.as_string())
                # Log as activity
                activity = Activity(subject=subject, type='Email', date=date, related_type='Customer', related_id=None, notes='Sent to: '+recipient+'\n'+body)
                db.session.add(activity)
                db.session.commit()
                msg = 'Email sent and logged as activity.'
            except Exception as e:
                msg = 'Error sending email: ' + str(e)
        # Add activity
        if 'add_activity' in request.form:
            subject = request.form.get('activity_subject')
            type_ = request.form.get('activity_type')
            date = request.form.get('activity_date')
            related_type = request.form.get('activity_related_type')
            related_id = request.form.get('activity_related_id')
            notes = request.form.get('activity_notes')
            if subject and date:
                activity = Activity(subject=subject, type=type_, date=date, related_type=related_type, related_id=related_id, notes=notes)
                db.session.add(activity)
                db.session.commit()
                msg = 'Activity added.'
            else:
                msg = 'Subject and Date required for activity.'
        # Move deal stage
        if 'move_deal' in request.form:
            deal_id = request.form.get('deal_id')
            new_stage = request.form.get('new_stage')
            deal = Deal.query.get(deal_id)
            if deal and new_stage:
                deal.stage = new_stage
                db.session.commit()
                msg = 'Deal moved to stage: ' + new_stage
        # Add lead
        if 'add_lead' in request.form:
            name = request.form.get('lead_name')
            email = request.form.get('lead_email')
            phone = request.form.get('lead_phone')
            company = request.form.get('lead_company')
            status = request.form.get('lead_status', 'New')
            notes = request.form.get('lead_notes', '')
            if name and email:
                lead = Lead(name=name, email=email, phone=phone, company=company, status=status, notes=notes)
                db.session.add(lead)
                db.session.commit()
                msg = 'Lead added.'
            else:
                msg = 'Name and Email required for lead.'
        # Add customer from main form
        if 'add_customer' in request.form:
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            status = request.form.get('status', 'Lead')
            notes = request.form.get('notes', '')
            if name and email:
                customer = Customer(name=name, email=email, phone=phone, status=status, notes=notes)
                db.session.add(customer)
                db.session.commit()
                msg = 'Customer added.'
            else:
                msg = 'Name and Email required.'
        # Add contact
        elif 'add_contact' in request.form:
            customer_id = request.form.get('customer_id')
            name = request.form.get('contact_name')
            email = request.form.get('contact_email')
            phone = request.form.get('contact_phone')
            role = request.form.get('contact_role')
            if customer_id and name:
                contact = Contact(customer_id=customer_id, name=name, email=email, phone=phone, role=role)
                db.session.add(contact)
                db.session.commit()
                msg = 'Contact added.'
        # Add task
        elif 'add_task' in request.form:
            customer_id = request.form.get('customer_id')
            title = request.form.get('task_title')
            description = request.form.get('task_description')
            due_date = request.form.get('task_due_date')
            status_ = request.form.get('task_status', 'Todo')
            if customer_id and title:
                task = Task(customer_id=customer_id, title=title, description=description, due_date=due_date, status=status_)
                db.session.add(task)
                db.session.commit()
                msg = 'Task added.'
        # Add deal
        elif 'add_deal' in request.form:
            customer_id = request.form.get('customer_id')
            title = request.form.get('deal_title')
            amount = request.form.get('deal_amount')
            stage = request.form.get('deal_stage', 'New')
            status_ = request.form.get('deal_status', 'Open')
            if customer_id and title:
                deal = Deal(customer_id=customer_id, title=title, amount=amount or 0, stage=stage, status=status_)
                db.session.add(deal)
                db.session.commit()
                msg = 'Deal added.'
        # Add reminder
        elif 'add_reminder' in request.form:
            customer_id = request.form.get('customer_id')
            message = request.form.get('reminder_message')
            due_date = request.form.get('reminder_due_date')
            if customer_id and message:
                reminder = Reminder(customer_id=customer_id, message=message, due_date=due_date)
                db.session.add(reminder)
                db.session.commit()
                msg = 'Reminder added.'
        # CSV import temporarily disabled (pandas not installed)
        # elif 'import_csv' in request.form and 'csv_file' in request.files:
        #     ...
        return redirect(url_for('home', tab=tab))
    # Export customers as CSV
    # export_url = url_for('export_customers')
    export_url = None  # CSV export temporarily disabled
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mukera CRM App</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    </head>
    <body class="bg-light">
        <div class="container my-5">
            <h1 class="mb-4"><a href="/" class="text-decoration-none">Mukera CRM App</a></h1>
            {% if msg %}<div class="alert alert-info">{{msg}}</div>{% endif %}
            <ul class="nav nav-tabs mb-4" id="crmTabs" role="tablist">
                <li class="nav-item"><a class="nav-link {% if tab=='marketing' %}active{% endif %}" href="?tab=marketing">Marketing</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='pipeline' %}active{% endif %}" href="?tab=pipeline">Pipeline</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='leads' %}active{% endif %}" href="?tab=leads">Leads</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='customers' %}active{% endif %}" href="?tab=customers">Customers</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='contacts' %}active{% endif %}" href="?tab=contacts">Contacts</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='tasks' %}active{% endif %}" href="?tab=tasks">Tasks</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='deals' %}active{% endif %}" href="?tab=deals">Deals</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='reminders' %}active{% endif %}" href="?tab=reminders">Reminders</a></li>
                <li class="nav-item"><a class="nav-link {% if tab=='activities' %}active{% endif %}" href="?tab=activities">Activities</a></li>
            </ul>
            <div class="tab-content">
                <div class="tab-pane fade {% if tab=='marketing' %}show active{% endif %}" id="marketing">
                    <h2 class="h5 mb-3">Campaigns</h2>
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_campaign" value="1">
                        <div class="row g-2">
                            <div class="col-md-3"><input type="text" class="form-control" name="campaign_name" placeholder="Campaign Name" required></div>
                            <div class="col-md-3"><input type="text" class="form-control" name="campaign_start" placeholder="Start Date (YYYY-MM-DD)"></div>
                            <div class="col-md-3"><input type="text" class="form-control" name="campaign_end" placeholder="End Date (YYYY-MM-DD)"></div>
                            <div class="col-md-3">
                                <select class="form-select" name="campaign_status">
                                    <option value="Draft">Draft</option>
                                    <option value="Active">Active</option>
                                    <option value="Completed">Completed</option>
                                </select>
                            </div>
                            <div class="col-md-12 mt-2"><textarea class="form-control" name="campaign_desc" placeholder="Description"></textarea></div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Campaign</button>
                    </form>
                    <table class="table table-bordered table-hover bg-white mb-5">
                        <thead class="table-light"><tr><th>Name</th><th>Status</th><th>Start</th><th>End</th><th>Description</th><th>Steps</th><th>Report</th><th>Delete</th></tr></thead>
                        <tbody>
                        {% for camp in campaigns %}
                        <tr>
                            <td>{{camp.name}}</td>
                            <td>{{camp.status}}</td>
                            <td>{{camp.start_date}}</td>
                            <td>{{camp.end_date}}</td>
                            <td>{{camp.description}}</td>
                            <td><a href="?tab=marketing&campaign_id={{camp.id}}">Steps</a></td>
                            <td><a href="?tab=marketing&campaign_id={{camp.id}}#report">Report</a></td>
                            <td><form method="POST" style="display:inline"><button name="delete_campaign" value="{{camp.id}}" class="btn btn-sm btn-danger">Delete</button></form></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                    <div class="card card-body mb-3">
                        {% if selected_campaign %}
                            <h3>Steps for: {{selected_campaign.name}}</h3>
                        {% else %}
                            <h3>Select a campaign to manage steps and reporting.</h3>
                        {% endif %}
                        <form method="POST" class="mb-3">
                            {% if selected_campaign %}
                                <input type="hidden" name="add_campaign_step" value="1">
                                <input type="hidden" name="campaign_id" value="{{selected_campaign.id}}">
                            {% endif %}
                            <div class="row g-2">
                                <div class="col-md-2">
                                    <select class="form-select" name="step_type">
                                        <option value="Email">Email</option>
                                        <option value="Wait">Wait</option>
                                    </select>
                                </div>
                                <div class="col-md-6"><input type="text" class="form-control" name="step_details" placeholder="For Email: subject|||body. For Wait: days."></div>
                                <div class="col-md-2"><input type="number" class="form-control" name="step_order" placeholder="Order" value="0"></div>
                                <div class="col-md-2"><button type="submit" class="btn btn-success">Add Step</button></div>
                            </div>
                        </form>
                        <table class="table table-bordered">
                            <thead><tr><th>Order</th><th>Type</th><th>Details</th><th>Delete</th></tr></thead>
                            <tbody>
                            {% for step in campaign_steps %}
                            <tr>
                                <td>{{step.order}}</td>
                                <td>{{step.step_type}}</td>
                                <td>{{step.details}}</td>
                                <td><form method="POST" style="display:inline"><button name="delete_campaign_step" value="{{step.id}}" class="btn btn-sm btn-danger">Delete</button></form></td>
                            </tr>
                            {% endfor %}
                            </tbody>
                        </table>
                        <form method="POST" class="row g-2 align-items-end mt-3">
                            {% if selected_campaign %}
                                <input type="hidden" name="run_campaign" value="1">
                                <input type="hidden" name="campaign_id" value="{{selected_campaign.id}}">
                            {% endif %}
                            <div class="col-md-4">
                                <select class="form-select" name="segment_id" required>
                                    <option value="">Select Segment</option>
                                    {% for seg in segments %}
                                    <option value="{{seg.id}}">{{seg.name}}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="col-md-4"><button type="submit" class="btn btn-primary">Run Campaign (Email Blast)</button></div>
                        </form>
                    </div>
                    <div id="report" class="card card-body mb-3">
                        {% if selected_campaign %}
                            <h3>Campaign Report: {{selected_campaign.name}}</h3>
                        {% else %}
                            <h3>Select a campaign to see its report.</h3>
                        {% endif %}
                        <table class="table table-bordered">
                            <thead><tr><th>Recipient</th><th>Step</th><th>Status</th><th>Time</th></tr></thead>
                            <tbody>
                            {% for log in campaign_logs %}
                            <tr>
                                <td>{{log.recipient_email}}</td>
                                <td>{{log.step_id}}</td>
                                <td>{{log.status}}</td>
                                <td>{{log.timestamp}}</td>
                            </tr>
                            {% endfor %}
                            </tbody>
                        </table>
                        {% if campaign_stats %}
                        <div class="mt-2">
                            <b>Total Targeted:</b> {{campaign_stats.targeted}} &nbsp; 
                            <b>Sent:</b> {{campaign_stats.sent}} &nbsp; 
                            <b>Failed:</b> {{campaign_stats.failed}} &nbsp; 
                            <b>Completed:</b> {{campaign_stats.completed}}
                        </div>
                        {% endif %}
                    </div>
                    <h2 class="h5 mb-3">Segments</h2>
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_segment" value="1">
                        <div class="row g-2">
                            <div class="col-md-4"><input type="text" class="form-control" name="segment_name" placeholder="Segment Name" required></div>
                            <div class="col-md-4">
                                <select class="form-select" name="segment_filter_type">
                                    <option value="Lead">Leads</option>
                                    <option value="Customer">Customers</option>
                                </select>
                            </div>
                            <div class="col-md-4"><input type="text" class="form-control" name="segment_filter_value" placeholder="Filter Value (status)"></div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Segment</button>
                    </form>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light"><tr><th>Name</th><th>Type</th><th>Value</th><th>Delete</th></tr></thead>
                        <tbody>
                        {% for seg in segments %}
                        <tr>
                            <td>{{seg.name}}</td>
                            <td>{{seg.filter_type}}</td>
                            <td>{{seg.filter_value}}</td>
                            <td><form method="POST" style="display:inline"><button name="delete_segment" value="{{seg.id}}" class="btn btn-sm btn-danger">Delete</button></form></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='pipeline' %}show active{% endif %}" id="pipeline">
                    <h2 class="h5 mb-3">Deals Pipeline</h2>
                    <div class="row">
                        {% for stage in ['New', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost'] %}
                        <div class="col">
                            <div class="card">
                                <div class="card-header bg-light"><b>{{stage}}</b></div>
                                <div class="card-body" style="min-height:150px;">
                                    {% for d in deals_by_stage[stage] %}
                                    <div class="card mb-2 border-primary">
                                        <div class="card-body p-2">
                                            <div><b>{{d.title}}</b> ({{d.amount}})</div>
                                            <div class="small">{{d.customer.name}}</div>
                                            <form method="POST" class="mt-1 d-flex align-items-center">
                                                <input type="hidden" name="move_deal" value="1">
                                                <input type="hidden" name="deal_id" value="{{d.id}}">
                                                <select name="new_stage" class="form-select form-select-sm me-1" onchange="this.form.submit()">
                                                    {% for s in ['New', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost'] %}
                                                        <option value="{{s}}" {% if d.stage==s %}selected{% endif %}>{{s}}</option>
                                                    {% endfor %}
                                                </select>
                                                <a href="{{ url_for('edit_deal', deal_id=d.id) }}" class="btn btn-sm btn-warning ms-1">Edit</a>
                                            </form>
                                        </div>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                <div class="tab-pane fade {% if tab=='leads' %}show active{% endif %}" id="leads">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_lead" value="1">
                        <h2 class="h5">Add Lead</h2>
                        <div class="row g-2">
                            <div class="col-md-3"><input type="text" class="form-control" name="lead_name" placeholder="Name" required></div>
                            <div class="col-md-3"><input type="email" class="form-control" name="lead_email" placeholder="Email" required></div>
                            <div class="col-md-2"><input type="text" class="form-control" name="lead_phone" placeholder="Phone"></div>
                            <div class="col-md-2"><input type="text" class="form-control" name="lead_company" placeholder="Company"></div>
                            <div class="col-md-2">
                                <select class="form-select" name="lead_status">
                                    <option value="New">New</option>
                                    <option value="Assigned">Assigned</option>
                                    <option value="Converted">Converted</option>
                                    <option value="Lost">Lost</option>
                                </select>
                            </div>
                            <div class="col-md-12 mt-2">
                                <textarea class="form-control" name="lead_notes" placeholder="Notes"></textarea>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Lead</button>
                    </form>
                    <h2 class="h5 mb-3">Leads</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Name</th><th>Email</th><th>Phone</th><th>Company</th><th>Status</th><th>Notes</th><th>Convert</th><th>Edit</th><th>Delete</th></tr>
                        </thead>
                        <tbody>
                        {% for l in leads %}
                        <tr>
                            <td>{{l.name}}</td>
                            <td>{{l.email}}</td>
                            <td>{{l.phone}}</td>
                            <td>{{l.company}}</td>
                            <td>{{l.status}}</td>
                            <td style="max-width:200px; white-space:pre-wrap;">{{l.notes}}</td>
                            <td><a href="{{ url_for('convert_lead', lead_id=l.id) }}" class="btn btn-sm btn-success">Convert</a></td>
                            <td><a href="{{ url_for('edit_lead', lead_id=l.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                            <td><a href="{{ url_for('delete_lead', lead_id=l.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='customers' %}show active{% endif %}" id="customers">
                    <form method="GET" class="row mb-3">
                        <div class="col-auto">
                            <input type="text" class="form-control" name="search" placeholder="Search by name or email" value="{{request.args.get('search', '')}}">
                        </div>
                        <div class="col-auto">
                            <button type="submit" class="btn btn-primary">Search</button>
                            <a href="/" class="btn btn-secondary">Clear</a>
                        </div>
                        <!-- CSV import/export temporarily disabled -->
                    </form>
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_customer" value="1">
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
                            <tr><th>Name</th><th>Email</th><th>Phone</th><th>Status</th><th>Notes</th></tr>
                        </thead>
                        <tbody>
                        {% for c in customers %}
                        <tr>
                            <td>{{c.name}}</td>
                            <td>{{c.email}}</td>
                            <td>{{c.phone}}</td>
                            <td>{{c.status}}</td>
                            <td style="max-width:200px; white-space:pre-wrap;">{{c.notes}}</td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='contacts' %}show active{% endif %}" id="contacts">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_contact" value="1">
                        <div class="row g-2">
                            <div class="col-md-3">
                                <select class="form-select" name="customer_id" required>
                                    <option value="">Select Customer</option>
                                    {% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3"><input type="text" class="form-control" name="contact_name" placeholder="Contact Name" required></div>
                            <div class="col-md-3"><input type="email" class="form-control" name="contact_email" placeholder="Contact Email"></div>
                            <div class="col-md-2"><input type="text" class="form-control" name="contact_phone" placeholder="Contact Phone"></div>
                            <div class="col-md-2"><input type="text" class="form-control" name="contact_role" placeholder="Role"></div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Contact</button>
                    </form>
                    <form method="GET" class="row mb-2">
                        <div class="col-auto">
                            <select class="form-select" name="contact_customer">
                                <option value="">All Customers</option>
                                {% for c in customers %}<option value="{{c.id}}" {% if request.args.get('contact_customer')==c.id|string %}selected{% endif %}>{{c.name}}</option>{% endfor %}
                            </select>
                        </div>
                        <div class="col-auto"><button type="submit" class="btn btn-secondary">Filter</button></div>
                    </form>
                    <h2 class="h5 mb-3">Contacts</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Customer</th><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Edit</th><th>Delete</th></tr>
                        </thead>
                        <tbody>
                        {% for ct in contacts %}
                        <tr>
                            <td>{{ct.customer.name}}</td>
                            <td>{{ct.name}}</td>
                            <td>{{ct.email}}</td>
                            <td>{{ct.phone}}</td>
                            <td>{{ct.role}}</td>
                            <td><a href="{{ url_for('edit_contact', contact_id=ct.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                            <td><a href="{{ url_for('delete_contact', contact_id=ct.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='tasks' %}show active{% endif %}" id="tasks">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_task" value="1">
                        <div class="row g-2">
                            <div class="col-md-3">
                                <select class="form-select" name="customer_id" required>
                                    <option value="">Select Customer</option>
                                    {% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3"><input type="text" class="form-control" name="task_title" placeholder="Task Title" required></div>
                            <div class="col-md-3"><input type="text" class="form-control" name="task_due_date" placeholder="Due Date (YYYY-MM-DD)"></div>
                            <div class="col-md-2">
                                <select class="form-select" name="task_status">
                                    <option value="Todo">Todo</option>
                                    <option value="In Progress">In Progress</option>
                                    <option value="Done">Done</option>
                                </select>
                            </div>
                            <div class="col-md-12 mt-2">
                                <textarea class="form-control" name="task_description" placeholder="Description"></textarea>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Task</button>
                    </form>
                    <form method="GET" class="row mb-2">
                        <div class="col-auto">
                            <select class="form-select" name="task_status">
                                <option value="">All Statuses</option>
                                <option value="Todo" {% if request.args.get('task_status')=='Todo' %}selected{% endif %}>Todo</option>
                                <option value="In Progress" {% if request.args.get('task_status')=='In Progress' %}selected{% endif %}>In Progress</option>
                                <option value="Done" {% if request.args.get('task_status')=='Done' %}selected{% endif %}>Done</option>
                            </select>
                        </div>
                        <div class="col-auto"><input type="text" class="form-control" name="task_due" placeholder="Due Date (YYYY-MM-DD)" value="{{request.args.get('task_due','')}}"></div>
                        <div class="col-auto"><button type="submit" class="btn btn-secondary">Filter</button></div>
                    </form>
                    <h2 class="h5 mb-3">Tasks</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Customer</th><th>Title</th><th>Due Date</th><th>Status</th><th>Description</th><th>Edit</th><th>Delete</th></tr>
                        </thead>
                        <tbody>
                        {% for t in tasks %}
                        <tr>
                            <td>{{t.customer.name}}</td>
                            <td>{{t.title}}</td>
                            <td>{{t.due_date}}</td>
                            <td>{{t.status}}</td>
                            <td>{{t.description}}</td>
                            <td><a href="{{ url_for('edit_task', task_id=t.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                            <td><a href="{{ url_for('delete_task', task_id=t.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='deals' %}show active{% endif %}" id="deals">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_deal" value="1">
                        <div class="row g-2">
                            <div class="col-md-3">
                                <select class="form-select" name="customer_id" required>
                                    <option value="">Select Customer</option>
                                    {% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3"><input type="text" class="form-control" name="deal_title" placeholder="Deal Title" required></div>
                            <div class="col-md-2"><input type="number" step="0.01" class="form-control" name="deal_amount" placeholder="Amount"></div>
                            <div class="col-md-2">
                                <select class="form-select" name="deal_stage">
                                    <option value="New">New</option>
                                    <option value="Qualified">Qualified</option>
                                    <option value="Won">Won</option>
                                    <option value="Lost">Lost</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <select class="form-select" name="deal_status">
                                    <option value="Open">Open</option>
                                    <option value="Closed">Closed</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Deal</button>
                    </form>
                    <form method="GET" class="row mb-2">
                        <div class="col-auto">
                            <select class="form-select" name="deal_stage">
                                <option value="">All Stages</option>
                                <option value="New" {% if request.args.get('deal_stage')=='New' %}selected{% endif %}>New</option>
                                <option value="Qualified" {% if request.args.get('deal_stage')=='Qualified' %}selected{% endif %}>Qualified</option>
                                <option value="Won" {% if request.args.get('deal_stage')=='Won' %}selected{% endif %}>Won</option>
                                <option value="Lost" {% if request.args.get('deal_stage')=='Lost' %}selected{% endif %}>Lost</option>
                            </select>
                        </div>
                        <div class="col-auto">
                            <select class="form-select" name="deal_status">
                                <option value="">All Statuses</option>
                                <option value="Open" {% if request.args.get('deal_status')=='Open' %}selected{% endif %}>Open</option>
                                <option value="Closed" {% if request.args.get('deal_status')=='Closed' %}selected{% endif %}>Closed</option>
                            </select>
                        </div>
                        <div class="col-auto"><button type="submit" class="btn btn-secondary">Filter</button></div>
                    </form>
                    <h2 class="h5 mb-3">Deals</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Customer</th><th>Title</th><th>Amount</th><th>Stage</th><th>Status</th><th>Edit</th><th>Delete</th></tr>
                        </thead>
                        <tbody>
                        {% for d in deals %}
                        <tr>
                            <td>{{d.customer.name}}</td>
                            <td>{{d.title}}</td>
                            <td>{{d.amount}}</td>
                            <td>{{d.stage}}</td>
                            <td>{{d.status}}</td>
                            <td><a href="{{ url_for('edit_deal', deal_id=d.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                            <td><a href="{{ url_for('delete_deal', deal_id=d.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='reminders' %}show active{% endif %}" id="reminders">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_reminder" value="1">
                        <div class="row g-2">
                            <div class="col-md-3">
                                <select class="form-select" name="customer_id" required>
                                    <option value="">Select Customer</option>
                                    {% for c in customers %}<option value="{{c.id}}">{{c.name}}</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-5"><input type="text" class="form-control" name="reminder_message" placeholder="Reminder Message" required></div>
                            <div class="col-md-3"><input type="text" class="form-control" name="reminder_due_date" placeholder="Due Date (YYYY-MM-DD)"></div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Reminder</button>
                    </form>
                    <form method="GET" class="row mb-2">
                        <div class="col-auto"><input type="text" class="form-control" name="reminder_due" placeholder="Due Date (YYYY-MM-DD)" value="{{request.args.get('reminder_due','')}}"></div>
                        <div class="col-auto">
                            <select class="form-select" name="reminder_completed">
                                <option value="">All</option>
                                <option value="yes" {% if request.args.get('reminder_completed')=='yes' %}selected{% endif %}>Completed</option>
                                <option value="no" {% if request.args.get('reminder_completed')=='no' %}selected{% endif %}>Not Completed</option>
                            </select>
                        </div>
                        <div class="col-auto"><button type="submit" class="btn btn-secondary">Filter</button></div>
                    </form>
                    <h2 class="h5 mb-3">Reminders</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Customer</th><th>Message</th><th>Due Date</th><th>Completed</th><th>Edit</th><th>Delete</th></tr>
                        </thead>
                        <tbody>
                        {% for r in reminders %}
                        <tr>
                            <td>{{r.customer.name}}</td>
                            <td>{{r.message}}</td>
                            <td>{{r.due_date}}</td>
                            <td>{{'Yes' if r.completed else 'No'}}</td>
                            <td><a href="{{ url_for('edit_reminder', reminder_id=r.id) }}" class="btn btn-sm btn-warning">Edit</a></td>
                            <td><a href="{{ url_for('delete_reminder', reminder_id=r.id) }}" class="btn btn-sm btn-danger">Delete</a></td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div class="tab-pane fade {% if tab=='activities' %}show active{% endif %}" id="activities">
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="add_activity" value="1">
                        <h2 class="h5">Add Activity</h2>
                        <div class="row g-2">
                            <div class="col-md-3"><input type="text" class="form-control" name="activity_subject" placeholder="Subject" required></div>
                            <div class="col-md-2">
                                <select class="form-select" name="activity_type">
                                    <option value="Call">Call</option>
                                    <option value="Meeting">Meeting</option>
                                    <option value="Task">Task</option>
                                    <option value="Email">Email</option>
                                </select>
                            </div>
                            <div class="col-md-2"><input type="text" class="form-control" name="activity_date" placeholder="Date (YYYY-MM-DD)" required></div>
                            <div class="col-md-2">
                                <select class="form-select" name="activity_related_type">
                                    <option value="">No Relation</option>
                                    <option value="Customer">Customer</option>
                                    <option value="Deal">Deal</option>
                                    <option value="Lead">Lead</option>
                                </select>
                            </div>
                            <div class="col-md-2"><input type="number" class="form-control" name="activity_related_id" placeholder="Related ID"></div>
                            <div class="col-md-12 mt-2">
                                <textarea class="form-control" name="activity_notes" placeholder="Notes"></textarea>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-success mt-3">Add Activity</button>
                    </form>
                    <form method="POST" class="card card-body mb-3">
                        <input type="hidden" name="send_email" value="1">
                        <h2 class="h5">Send Email</h2>
                        <div class="row g-2">
                            <div class="col-md-4"><input type="email" class="form-control" name="recipient" placeholder="Recipient Email" required></div>
                            <div class="col-md-4"><input type="text" class="form-control" name="subject" placeholder="Subject" required></div>
                            <div class="col-md-12 mt-2">
                                <textarea class="form-control" name="body" placeholder="Email Body" required></textarea>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary mt-3">Send Email</button>
                    </form>
                    <h2 class="h5 mb-3">Activities Calendar</h2>
                    <table class="table table-bordered table-hover bg-white">
                        <thead class="table-light">
                            <tr><th>Date</th><th>Type</th><th>Subject</th><th>Related</th><th>Notes</th></tr>
                        </thead>
                        <tbody>
                        {% for date, acts in activities_by_date.items() %}
                            {% for a in acts %}
                            <tr>
                                <td>{{a.date}}</td>
                                <td>{{a.type}}</td>
                                <td>{{a.subject}}</td>
                                <td>{{a.related_type}} {{a.related_id}}</td>
                                <td>{{a.notes}}</td>
                            </tr>
                            {% endfor %}
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''', customers=customers, contacts=contacts, tasks=tasks, deals=deals, reminders=reminders, tab=tab, msg=msg, export_url=export_url, deals_by_stage=deals_by_stage, activities_by_date=activities_by_date)

# --- Edit/Delete for Contacts ---
@app.route('/edit_contact/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if request.method == 'POST':
        contact.name = request.form.get('name')
        contact.email = request.form.get('email')
        contact.phone = request.form.get('phone')
        contact.role = request.form.get('role')
        db.session.commit()
        return redirect(url_for('home', tab='contacts'))
    return render_template_string('''<form method="POST" class="container mt-5"><h3>Edit Contact</h3>
        <input type="text" name="name" value="{{contact.name}}" required class="form-control mb-2">
        <input type="email" name="email" value="{{contact.email}}" class="form-control mb-2">
        <input type="text" name="phone" value="{{contact.phone}}" class="form-control mb-2">
        <input type="text" name="role" value="{{contact.role}}" class="form-control mb-2">
        <button type="submit" class="btn btn-success">Save</button>
        <a href="{{ url_for('home', tab='contacts') }}" class="btn btn-secondary">Cancel</a>
    </form>''', contact=contact)

@app.route('/delete_contact/<int:contact_id>')
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('home', tab='contacts'))

# --- Edit/Delete for Tasks ---
@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        task.due_date = request.form.get('due_date')
        task.status = request.form.get('status')
        db.session.commit()
        return redirect(url_for('home', tab='tasks'))
    return render_template_string('''<form method="POST" class="container mt-5"><h3>Edit Task</h3>
        <input type="text" name="title" value="{{task.title}}" required class="form-control mb-2">
        <input type="text" name="due_date" value="{{task.due_date}}" class="form-control mb-2">
        <select name="status" class="form-select mb-2">
            <option value="Todo" {% if task.status=='Todo' %}selected{% endif %}>Todo</option>
            <option value="In Progress" {% if task.status=='In Progress' %}selected{% endif %}>In Progress</option>
            <option value="Done" {% if task.status=='Done' %}selected{% endif %}>Done</option>
        </select>
        <textarea name="description" class="form-control mb-2">{{task.description}}</textarea>
        <button type="submit" class="btn btn-success">Save</button>
        <a href="{{ url_for('home', tab='tasks') }}" class="btn btn-secondary">Cancel</a>
    </form>''', task=task)

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('home', tab='tasks'))

# --- Edit/Delete for Deals ---
@app.route('/edit_deal/<int:deal_id>', methods=['GET', 'POST'])
def edit_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    if request.method == 'POST':
        deal.title = request.form.get('title')
        deal.amount = float(request.form.get('amount') or 0)
        deal.stage = request.form.get('stage')
        deal.status = request.form.get('status')
        db.session.commit()
        return redirect(url_for('home', tab='deals'))
    return render_template_string('''<form method="POST" class="container mt-5"><h3>Edit Deal</h3>
        <input type="text" name="title" value="{{deal.title}}" required class="form-control mb-2">
        <input type="number" step="0.01" name="amount" value="{{deal.amount}}" class="form-control mb-2">
        <select name="stage" class="form-select mb-2">
            <option value="New" {% if deal.stage=='New' %}selected{% endif %}>New</option>
            <option value="Qualified" {% if deal.stage=='Qualified' %}selected{% endif %}>Qualified</option>
            <option value="Won" {% if deal.stage=='Won' %}selected{% endif %}>Won</option>
            <option value="Lost" {% if deal.stage=='Lost' %}selected{% endif %}>Lost</option>
        </select>
        <select name="status" class="form-select mb-2">
            <option value="Open" {% if deal.status=='Open' %}selected{% endif %}>Open</option>
            <option value="Closed" {% if deal.status=='Closed' %}selected{% endif %}>Closed</option>
        </select>
        <button type="submit" class="btn btn-success">Save</button>
        <a href="{{ url_for('home', tab='deals') }}" class="btn btn-secondary">Cancel</a>
    </form>''', deal=deal)

@app.route('/delete_deal/<int:deal_id>')
def delete_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    db.session.delete(deal)
    db.session.commit()
    return redirect(url_for('home', tab='deals'))

# --- Edit/Delete for Reminders ---
@app.route('/edit_reminder/<int:reminder_id>', methods=['GET', 'POST'])
def edit_reminder(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    if request.method == 'POST':
        reminder.message = request.form.get('message')
        reminder.due_date = request.form.get('due_date')
        reminder.completed = bool(request.form.get('completed'))
        db.session.commit()
        return redirect(url_for('home', tab='reminders'))
    return render_template_string('''<form method="POST" class="container mt-5"><h3>Edit Reminder</h3>
        <input type="text" name="message" value="{{reminder.message}}" required class="form-control mb-2">
        <input type="text" name="due_date" value="{{reminder.due_date}}" class="form-control mb-2">
        <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" name="completed" id="completed" {% if reminder.completed %}checked{% endif %}>
            <label class="form-check-label" for="completed">Completed</label>
        </div>
        <button type="submit" class="btn btn-success">Save</button>
        <a href="{{ url_for('home', tab='reminders') }}" class="btn btn-secondary">Cancel</a>
    </form>''', reminder=reminder)

@app.route('/delete_reminder/<int:reminder_id>')
def delete_reminder(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    db.session.delete(reminder)
    db.session.commit()
    return redirect(url_for('home', tab='reminders'))

# --- Lead CRUD and Conversion ---
@app.route('/edit_lead/<int:lead_id>', methods=['GET', 'POST'])
def edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if request.method == 'POST':
        lead.name = request.form.get('name')
        lead.email = request.form.get('email')
        lead.phone = request.form.get('phone')
        lead.company = request.form.get('company')
        lead.status = request.form.get('status')
        lead.notes = request.form.get('notes')
        db.session.commit()
        return redirect(url_for('home', tab='leads'))
    return render_template_string('''<form method="POST" class="container mt-5"><h3>Edit Lead</h3>
        <input type="text" name="name" value="{{lead.name}}" required class="form-control mb-2">
        <input type="email" name="email" value="{{lead.email}}" required class="form-control mb-2">
        <input type="text" name="phone" value="{{lead.phone}}" class="form-control mb-2">
        <input type="text" name="company" value="{{lead.company}}" class="form-control mb-2">
        <select name="status" class="form-select mb-2">
            <option value="New" {% if lead.status=='New' %}selected{% endif %}>New</option>
            <option value="Assigned" {% if lead.status=='Assigned' %}selected{% endif %}>Assigned</option>
            <option value="Converted" {% if lead.status=='Converted' %}selected{% endif %}>Converted</option>
            <option value="Lost" {% if lead.status=='Lost' %}selected{% endif %}>Lost</option>
        </select>
        <textarea name="notes" class="form-control mb-2">{{lead.notes}}</textarea>
        <button type="submit" class="btn btn-success">Save</button>
        <a href="{{ url_for('home', tab='leads') }}" class="btn btn-secondary">Cancel</a>
    </form>''', lead=lead)

@app.route('/delete_lead/<int:lead_id>')
def delete_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return redirect(url_for('home', tab='leads'))

@app.route('/convert_lead/<int:lead_id>')
def convert_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    # Create customer from lead
    customer = Customer(name=lead.name, email=lead.email, phone=lead.phone, status='Lead', notes=lead.notes)
    db.session.add(customer)
    db.session.commit()
    # Optionally, create a contact as well
    contact = Contact(customer_id=customer.id, name=lead.name, email=lead.email, phone=lead.phone, role='Primary')
    db.session.add(contact)
    db.session.commit()
    # Mark lead as converted or delete
    db.session.delete(lead)
    db.session.commit()
    return redirect(url_for('home', tab='customers'))

@app.route('/customer/<int:customer_id>/edit', methods=['GET', 'POST'])
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

# @app.route('/export_customers')
# def export_customers():
#     ... # CSV export temporarily disabled

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
