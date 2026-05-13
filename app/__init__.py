from flask import Flask
from flask_mysqldb import MySQL
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config
import os

mysql = MySQL()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    mysql.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access PHRMS.'
    login_manager.login_message_category = 'info'

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.hr import hr_bp
    from app.routes import (
        employee_bp, attendance_bp, leave_bp,
        payroll_bp, payslip_bp, ctc_bp,
        separation_bp, iou_bp, foodcoupon_bp,
        npr_bp, recruitment_bp, grievance_bp,
        kpi_bp, travel_bp, reports_bp,
        admin_attr_bp, user_mgmt_bp, api_bp
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,        url_prefix='/admin')
    app.register_blueprint(hr_bp,           url_prefix='/hr')
    app.register_blueprint(employee_bp,     url_prefix='/employee')
    app.register_blueprint(attendance_bp,   url_prefix='/attendance')
    app.register_blueprint(leave_bp,        url_prefix='/leave')
    app.register_blueprint(payroll_bp,      url_prefix='/payroll')
    app.register_blueprint(payslip_bp,      url_prefix='/payslip')
    app.register_blueprint(ctc_bp,          url_prefix='/ctc')
    app.register_blueprint(separation_bp,   url_prefix='/separation')
    app.register_blueprint(iou_bp,          url_prefix='/iou')
    app.register_blueprint(foodcoupon_bp,   url_prefix='/foodcoupon')
    app.register_blueprint(npr_bp,          url_prefix='/npr')
    app.register_blueprint(recruitment_bp,  url_prefix='/recruitment')
    app.register_blueprint(grievance_bp,    url_prefix='/grievance')
    app.register_blueprint(kpi_bp,          url_prefix='/kpi')
    app.register_blueprint(travel_bp,       url_prefix='/travel')
    app.register_blueprint(reports_bp,      url_prefix='/reports')
    app.register_blueprint(admin_attr_bp,   url_prefix='/admin-attr')
    app.register_blueprint(user_mgmt_bp,    url_prefix='/users')
    app.register_blueprint(api_bp,          url_prefix='/api')

    return app
