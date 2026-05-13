from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import check_password_hash
from app import login_manager, mysql
from app.db import get_user_by_username, get_user_by_id
import hashlib

auth_bp = Blueprint('auth', __name__)


class User(UserMixin):
    def __init__(self, data):
        self.id = data['userid']
        self.userid = data['userid']
        self.username = data['username']
        self.usertype = data.get('usertype', '')
        self.roleid = data.get('roleid')
        self.rolename = data.get('rolename', '')
        self.employeeid = data.get('employeeid')
        self.employeenumber = data.get('employeenumber')
        self.firstname = data.get('firstname', '')
        self.lastname = data.get('lastname', '')
        self.fullname = f"{data.get('firstname','')} {data.get('lastname','')}".strip()
        self.mobileaccess = data.get('mobileaccess', 0)
        self.mobileattendanceflag = data.get('mobileattendanceflag', 0)
        self.activestatus = data.get('activestatus', 1)
        self.gradeid = data.get('gradeid')
        self.branchid = data.get('branchid')
        self.departmentid = data.get('departmentid')
        self.businessunit = data.get('businessunit')

    @property
    def is_admin(self):
        return self.usertype in ('Admin', 'Super Admin') or self.roleid == 1

    @property
    def is_hr(self):
        return 'HR' in (self.rolename or '') or self.usertype in ('HR',)

    @property
    def is_employee(self):
        return not self.is_admin and not self.is_hr

    def get_dashboard_url(self):
        if self.is_admin:
            return url_for('admin.dashboard')
        elif self.is_hr:
            return url_for('hr.dashboard')
        else:
            return url_for('employee.dashboard')


@login_manager.user_loader
def load_user(userid):
    data = get_user_by_id(int(userid))
    if data:
        return User(data)
    return None


def verify_password(stored_hash, plain):
    """Proconnect uses MD5 or SHA1 for legacy passwords — try both."""
    md5 = hashlib.md5(plain.encode()).hexdigest()
    sha1 = hashlib.sha1(plain.encode()).hexdigest()
    sha256 = hashlib.sha256(plain.encode()).hexdigest()
    return stored_hash in (md5, sha1, sha256, plain) or check_password_hash(stored_hash, plain)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(current_user.get_dashboard_url())

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user_data = get_user_by_username(username)

        if not user_data:
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html')

        if not user_data.get('activestatus'):
            flash('Your account is inactive. Contact HR.', 'warning')
            return render_template('auth/login.html')

        if not verify_password(user_data['pwd'], password):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html')

        user = User(user_data)
        login_user(user, remember=remember)
        session['login_time'] = str(__import__('datetime').datetime.now())

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(user.get_dashboard_url())

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')

        from app.db import get_user_by_id, execute
        user_data = get_user_by_id(current_user.userid)

        if not verify_password(user_data['pwd'], current_pw):
            flash('Current password is incorrect.', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        elif len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'danger')
        else:
            import hashlib
            new_hash = hashlib.md5(new_pw.encode()).hexdigest()
            execute("UPDATE users SET pwd=%s, modifiedby=%s, modifieddatetime=NOW() WHERE userid=%s",
                    (new_hash, current_user.username, current_user.userid))
            flash('Password changed successfully.', 'success')
            return redirect(current_user.get_dashboard_url())

    return render_template('auth/change_password.html')
