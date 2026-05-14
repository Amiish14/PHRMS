from flask import Flask, render_template, request, jsonify
from flask_mysqldb import MySQL
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from config import config
import os
import sys
import datetime
import logging
import traceback

mysql = MySQL()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── LOGGING ─────────────────────────────────────────────────────────────
    # Force logs to stdout so Render captures them. Default Flask logger
    # buffers and swallows tracebacks — this fixes that.
    if not app.debug:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        ))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        # Also send werkzeug/sqlalchemy logs to stdout
        logging.getLogger('werkzeug').setLevel(logging.INFO)

    mysql.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access PHRMS.'
    login_manager.login_message_category = 'info'

    @app.context_processor
    def inject_globals():
        return {'now': datetime.datetime.now(), 'today': datetime.date.today()}

    # ── BLUEPRINTS ──────────────────────────────────────────────────────────
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

    # ── GLOBAL ERROR HANDLERS ───────────────────────────────────────────────
    # These ensure the user NEVER sees the raw "Internal Server Error" page
    # again, regardless of what crashes.

    def _is_super_admin():
        """Only Nilesh (DIR12010) or anyone with usertype 'Admin' / 'Super Admin'
        gets to see the raw traceback in the browser."""
        try:
            if not current_user.is_authenticated:
                return False
            if current_user.username == 'DIR12010':
                return True
            return current_user.usertype in ('Admin', 'Super Admin')
        except Exception:
            return False

    def _render_error(code, title, message, exc=None):
        """Render the friendly error page. Show traceback only to super admin."""
        tb = None
        if exc is not None and _is_super_admin():
            tb = traceback.format_exc()
        # Log full traceback for Render logs no matter what
        if exc is not None:
            app.logger.error(
                "Error %s on %s — %s\n%s",
                code, request.path, message, traceback.format_exc()
            )
        # If the request was JSON / API, return JSON
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': code, 'message': message}), code
        try:
            return render_template(
                'error.html',
                code=code, title=title, message=message,
                traceback_text=tb, path=request.path,
            ), code
        except Exception:
            # Template itself failed — last resort plain HTML
            tb_html = (
                "<pre style='white-space:pre-wrap;background:#fdeaea;padding:12px;"
                "border-radius:6px;font-size:12px'>" + (tb or '') + "</pre>"
            ) if tb else ''
            return (
                f"<html><body style='font-family:system-ui;max-width:680px;"
                f"margin:60px auto;color:#212529'>"
                f"<h1 style='color:#c0392b'>{title}</h1>"
                f"<p>{message}</p>"
                f"<p><a href='/' style='color:#1565c0'>Back to home</a></p>"
                f"{tb_html}"
                f"</body></html>",
                code,
            )

    @app.errorhandler(404)
    def err_404(e):
        return _render_error(
            404, 'Page not found',
            "The page you tried to open doesn't exist. It may have been moved.",
        )

    @app.errorhandler(403)
    def err_403(e):
        return _render_error(
            403, 'Access denied',
            "You don't have permission to view this page.",
        )

    @app.errorhandler(500)
    def err_500(e):
        return _render_error(
            500, 'Something went wrong',
            "We hit an unexpected error. Our team has been notified. "
            "Try refreshing — if it persists, check the System Health page.",
            exc=e,
        )

    @app.errorhandler(Exception)
    def err_any(e):
        # Catch-all for anything else (DB errors, template errors, etc.)
        # Don't catch HTTPException — let Flask handle 404/403/etc.
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        return _render_error(
            500, 'Something went wrong',
            "We hit an unexpected error. Try refreshing — if it persists, "
            "use System Health to check the database.",
            exc=e,
        )

    # ── HEALTH CHECK ────────────────────────────────────────────────────────
    @app.route('/_health')
    def health():
        """Public health check. Returns DB connection status + version.
        Open this URL anytime to confirm whether MySQL is reachable from Render.
        Returns HTTP 503 when the DB is unreachable so you can wire it up to
        an uptime monitor too."""
        out = {
            'status': 'ok',
            'app': 'PHRMS',
            'time': datetime.datetime.now().isoformat(),
            'db': {'connected': False, 'error': None},
            'config': {
                'mysql_host': app.config.get('MYSQL_HOST'),
                'mysql_port': app.config.get('MYSQL_PORT'),
                'mysql_db':   app.config.get('MYSQL_DB'),
                'mysql_user': app.config.get('MYSQL_USER'),
            },
        }
        # Try a real connection — by-passes the safe wrapper in db.q()
        try:
            import MySQLdb
            kwargs = {
                'host': app.config['MYSQL_HOST'],
                'port': int(app.config.get('MYSQL_PORT') or 3306),
                'user': app.config['MYSQL_USER'],
                'passwd': app.config.get('MYSQL_PASSWORD') or '',
                'db': app.config['MYSQL_DB'],
                'connect_timeout': 5,
            }
            conn = MySQLdb.connect(**kwargs)
            cur = conn.cursor()
            cur.execute("SELECT VERSION(), DATABASE(), NOW()")
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                out['db'] = {
                    'connected': True,
                    'version': str(row[0]),
                    'database': str(row[1]),
                    'server_time': str(row[2]),
                }
        except Exception as ex:
            out['status'] = 'degraded'
            out['db'] = {
                'connected': False,
                'error': f"{type(ex).__name__}: {ex}",
            }
        http_code = 200 if out['db']['connected'] else 503
        return jsonify(out), http_code

    return app