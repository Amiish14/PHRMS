from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from app import db as DB
import datetime

admin_bp = Blueprint("admin", __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = DB.get_admin_dashboard_stats()
    verticals = DB.get_headcount_by_vertical()
    leave_summary = DB.get_leave_summary_current_month()
    mobile_checkins = DB.get_todays_mobile_checkins()
    birthdays = DB.get_birthdays_this_week()
    recent_joiners = DB.get_recent_joiners(8)
    fiscal = DB.get_current_fiscal_year()
    return render_template("admin/dashboard.html",
        stats=stats, verticals=verticals,
        leave_summary=leave_summary, mobile_checkins=mobile_checkins,
        birthdays=birthdays, recent_joiners=recent_joiners, fiscal=fiscal)

@admin_bp.route("/employees")
@login_required
@admin_required
def employees():
    page = int(request.args.get("page", 1))
    search = request.args.get("q", "")
    dept = request.args.get("dept")
    vertical = request.args.get("vertical")
    active_only = request.args.get("active", "1") == "1"
    result = DB.get_employees(page=page, search=search, dept=dept,
                               vertical=vertical, active_only=active_only)
    depts = DB.get_departments()
    verticals = DB.get_verticals()
    grades = DB.get_grades()
    branches = DB.get_branches()
    return render_template("admin/employees.html", result=result,
        depts=depts, verticals=verticals, grades=grades, branches=branches,
        search=search)

@admin_bp.route("/employee/<int:empid>")
@login_required
@admin_required
def employee_profile(empid):
    emp = DB.get_employee_full_profile(empid)
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("admin.employees"))
    loans = DB.get_employee_loans(empid)
    return render_template("admin/employee_profile.html", emp=emp, loans=loans)

@admin_bp.route("/attendance")
@login_required
@admin_required
def attendance():
    from app.db import q
    date_str = request.args.get("date", "")
    try:
        selected_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date(2022, 10, 28)
    except Exception:
        selected_date = datetime.date(2022, 10, 28)
    records = q("""
        SELECT da.attendanceid, da.employeeid, da.attendancedate,
               da.ismobile, da.isreqularize,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname,
               bu.businessunitname as vertical,
               at.typename as atttype, at.typecolour,
               lt.typename as leavetype,
               mar.resaon as mobile_reason, mar.lat, mar.lng, mar.address,
               mar.createddatetime as checkin_time
        FROM dailyattendance da
        JOIN employees e ON da.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        JOIN attendancetypes at ON da.attendancetypeid = at.typeid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        LEFT JOIN businessunit bu ON e.businessunit = bu.businessunitid
        LEFT JOIN leavetypes lt ON da.leavetypeid = lt.typeid
        LEFT JOIN mobileattendancereason mar ON da.employeeid=mar.employeeid
            AND da.attendancedate=mar.attendancedate AND mar.recordstatus=1
        WHERE da.attendancedate = %s AND da.recordstatus=1
        ORDER BY empname
    """, (selected_date,))
    present_count = sum(1 for r in records if "Present" in r.get("atttype",""))
    leave_count = sum(1 for r in records if "Leave" in r.get("atttype",""))
    mobile_count = sum(1 for r in records if r.get("ismobile"))
    stats = DB.get_admin_dashboard_stats()
    reg_requests = DB.get_attendance_regulation_requests(status="pending", limit=20)
    return render_template("admin/attendance.html",
        records=records, stats=stats, reg_requests=reg_requests,
        selected_date=selected_date, present_count=present_count,
        leave_count=leave_count, mobile_count=mobile_count)

@admin_bp.route("/leave-approvals")
@login_required
@admin_required
def leave_approvals():
    status = request.args.get("status", "pending")
    page = int(request.args.get("page", 1))
    result = DB.get_leave_requests(status=status or None, page=page)
    return render_template("admin/leave_approvals.html", result=result, status=status)

@admin_bp.route("/leave-approvals/<int:lrid>/action", methods=["POST"])
@login_required
@admin_required
def leave_action(lrid):
    action = request.form.get("action")
    DB.approve_leave(lrid, current_user.employeeid, approve=(action == "approve"))
    flash("Leave approved." if action=="approve" else "Leave rejected.", "success")
    return redirect(url_for("admin.leave_approvals"))

@admin_bp.route("/recruitment")
@login_required
@admin_required
def recruitment():
    result = DB.get_recruitment_requests()
    return render_template("admin/recruitment.html", result=result)

@admin_bp.route("/grievances")
@login_required
@admin_required
def grievances():
    result = DB.get_grievances()
    return render_template("admin/grievances.html", result=result)

@admin_bp.route("/kpi")
@login_required
@admin_required
def kpi():
    fiscal = DB.get_current_fiscal_year()
    fy = request.args.get("fy", fiscal["fiscalvalue"] if fiscal else "")
    targets = DB.get_kpi_targets(fiscalyear=fy)
    fiscal_years = DB.get_fiscal_years()
    return render_template("admin/kpi.html", targets=targets,
                           fiscal_years=fiscal_years, fy=fy)

@admin_bp.route("/holidays")
@login_required
@admin_required
def holidays():
    year = int(request.args.get("year", datetime.date.today().year))
    holidays = DB.get_holidays(year=year)
    years = list(range(2015, datetime.date.today().year + 2))
    return render_template("admin/holidays.html", holidays=holidays,
                           year=year, years=years)
