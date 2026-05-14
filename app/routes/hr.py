from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from app import db as DB
import datetime

hr_bp = Blueprint('hr', __name__)

def hr_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_hr or current_user.is_admin):
            flash('HR access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@hr_bp.route('/dashboard')
@login_required
@hr_required
def dashboard():
    today = datetime.date.today()
    stats = DB.get_admin_dashboard_stats()
    verticals = DB.get_headcount_by_vertical()
    pending_leaves = DB.get_leave_requests(status='pending', per_page=5)
    mobile_checkins = DB.get_todays_mobile_checkins()
    reg_requests = DB.get_attendance_regulation_requests(status='pending', limit=5)
    recent_joiners = DB.get_recent_joiners(6)
    birthdays = DB.get_birthdays_this_week()
    leave_summary = DB.get_leave_summary_current_month()
    return render_template('hr/dashboard.html',
        stats=stats, verticals=verticals, today=today,
        pending_leaves=pending_leaves['rows'],
        mobile_checkins=mobile_checkins,
        reg_requests=reg_requests,
        recent_joiners=recent_joiners,
        birthdays=birthdays,
        leave_summary=leave_summary)

@hr_bp.route('/employees')
@login_required
@hr_required
def employees():
    page = int(request.args.get('page', 1))
    search = request.args.get('q', '')
    dept = request.args.get('dept')
    active_only = request.args.get('active', '1') == '1'
    result = DB.get_employees(page=page, search=search, dept=dept, active_only=active_only)
    depts = DB.get_departments()
    return render_template('hr/employees.html', result=result, depts=depts, search=search)

@hr_bp.route('/employee/<int:empid>')
@login_required
@hr_required
def employee_profile(empid):
    emp = DB.get_employee_full_profile(empid)
    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('hr.employees'))
    today = datetime.date.today()
    leave_balance = DB.get_leave_balance(empid)
    attendance = DB.get_attendance_for_month(empid, today.year, today.month)
    return render_template('hr/employee_profile.html', emp=emp,
        leave_balance=leave_balance, attendance=attendance,
        year=today.year, month=today.month)

@hr_bp.route('/attendance')
@login_required
@hr_required
def attendance():
    from app.db import q
    date_str = request.args.get('date', '')
    try:
        selected_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date(2022, 10, 28)
    except Exception:
        selected_date = datetime.date(2022, 10, 28)
    records = q("""
        SELECT da.*, at.typename as atttype, at.typecolour,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname,
               bu.businessunitname as vertical,
               mar.address, mar.lat, mar.lng
        FROM dailyattendance da
        JOIN employees e ON da.employeeid=e.employeeid
        JOIN contact c ON e.contactid=c.contactid
        JOIN attendancetypes at ON da.attendancetypeid=at.typeid
        LEFT JOIN departments d ON e.departmentid=d.departmentid
        LEFT JOIN businessunit bu ON e.businessunit=bu.businessunitid
        LEFT JOIN mobileattendancereason mar ON da.employeeid=mar.employeeid
            AND da.attendancedate=mar.attendancedate AND mar.recordstatus=1
        WHERE da.attendancedate=%s AND da.recordstatus=1
        ORDER BY empname
    """, (selected_date,))
    present_count = sum(1 for r in records if 'Present' in r.get('atttype',''))
    leave_count = sum(1 for r in records if 'Leave' in r.get('atttype',''))
    mobile_count = sum(1 for r in records if r.get('ismobile'))
    stats = DB.get_admin_dashboard_stats()
    reg_requests = DB.get_attendance_regulation_requests(status='pending', limit=20)
    return render_template('hr/attendance.html',
        records=records, stats=stats, reg_requests=reg_requests,
        selected_date=selected_date, present_count=present_count,
        leave_count=leave_count, mobile_count=mobile_count)

@hr_bp.route('/leave-management')
@login_required
@hr_required
def leave_management():
    status = request.args.get('status', 'pending')
    page = int(request.args.get('page', 1))
    result = DB.get_leave_requests(status=status or None, page=page)
    return render_template('hr/leave_management.html', result=result, status=status)

@hr_bp.route('/approve-leave/<int:lrid>', methods=['POST'])
@login_required
@hr_required
def approve_leave(lrid):
    action = request.form.get('action', 'approve')
    DB.approve_leave(lrid, current_user.employeeid, approve=(action == 'approve'))
    flash(f"Leave {'approved' if action=='approve' else 'rejected'}.", 'success')
    return redirect(url_for('hr.leave_management'))

@hr_bp.route('/recruitment')
@login_required
@hr_required
def recruitment():
    result = DB.get_recruitment_requests()
    return render_template('hr/recruitment.html', result=result)

@hr_bp.route('/grievances')
@login_required
@hr_required
def grievances():
    result = DB.get_grievances()
    return render_template('hr/grievances.html', result=result)