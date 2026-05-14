"""
All blueprints — complete PHRMS matching original Proconnect functionality.
Modules: Employee, Attendance, Leave, Payslip, CTC, Separation, IOU,
         Food Coupon, NPR, Recruitment, Grievance, KPI, Travel, Reports,
         Admin Attributes, User Management, Org Structure
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
import datetime
from app import db as DB


# ─── EMPLOYEE ────────────────────────────────────────────────────────────────
employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/dashboard')
@login_required
def dashboard():
    empid = current_user.employeeid
    if not empid:
        flash('No employee record linked.', 'warning')
        return redirect(url_for('auth.logout'))
    today = datetime.date.today()
    att_summary = DB.get_attendance_summary_for_employee(empid, year=today.year)
    leave_balance = DB.get_leave_balance(empid)
    my_leaves = DB.get_leave_requests(employeeid=empid, per_page=5)
    my_loans = DB.get_employee_loans(empid)
    attendance = DB.get_attendance_for_month(empid, today.year, today.month)
    my_claims = DB.get_claim_payments(employeeid=empid, per_page=5)
    return render_template('employee/dashboard.html',
        att_summary=att_summary, leave_balance=leave_balance,
        my_leaves=my_leaves['rows'], my_loans=my_loans,
        attendance=attendance, my_claims=my_claims['rows'],
        leave_types=DB.get_leave_types(),
        now=datetime.datetime.now())

@employee_bp.route('/profile')
@login_required
def profile():
    emp = DB.get_employee_full_profile(current_user.employeeid)
    return render_template('employee/profile.html', emp=emp)

@employee_bp.route('/my-attendance')
@login_required
def my_attendance():
    empid = current_user.employeeid
    today = datetime.date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))
    attendance = DB.get_attendance_for_month(empid, year, month)
    summary = DB.get_attendance_summary_for_employee(empid, year=year)
    mobile_history = DB.get_mobile_attendance_history(employeeid=empid, limit=30)
    return render_template('employee/attendance.html',
        attendance=attendance, summary=summary,
        mobile_history=mobile_history, year=year, month=month)

@employee_bp.route('/my-leave')
@login_required
def my_leave():
    empid = current_user.employeeid
    page = int(request.args.get('page', 1))
    status = request.args.get('status', '')
    result = DB.get_leave_requests(employeeid=empid, status=status or None, page=page)
    balance = DB.get_leave_balance(empid)
    leave_types = DB.get_leave_types()
    return render_template('employee/leave.html', result=result, balance=balance,
                           leave_types=leave_types, status=status)

@employee_bp.route('/apply-leave', methods=['POST'])
@login_required
def apply_leave():
    empid = current_user.employeeid
    leavetypeid = request.form.get('leavetypeid')
    startdate = request.form.get('startdate')
    enddate = request.form.get('enddate')
    reason = request.form.get('reason', '')
    contact_details = request.form.get('contact_details', '')
    try:
        sd = datetime.date.fromisoformat(startdate)
        ed = datetime.date.fromisoformat(enddate)
        noofdays = (ed - sd).days + 1
        leave_num = f"LR{empid}{datetime.date.today().strftime('%Y%m%d%H%M%S')}"
        DB.submit_leave_request(empid, leavetypeid, startdate, enddate,
                                noofdays, reason, contact_details,
                                current_user.username, leave_num)
        flash('Leave request submitted successfully.', 'success')
    except Exception as ex:
        flash(f'Error: {ex}', 'danger')
    return redirect(url_for('employee.my_leave'))

@employee_bp.route('/my-claims')
@login_required
def my_claims():
    empid = current_user.employeeid
    page = int(request.args.get('page', 1))
    result = DB.get_claim_payments(employeeid=empid, page=page)
    return render_template('employee/claims.html', result=result)

@employee_bp.route('/my-loans')
@login_required
def my_loans():
    loans = DB.get_employee_loans(current_user.employeeid)
    return render_template('employee/loans.html', loans=loans)

@employee_bp.route('/my-iou')
@login_required
def my_iou():
    from app.db import q
    empid = current_user.employeeid
    rows = q("""
        SELECT ir.*, CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname
        FROM iourequest ir
        JOIN employees e ON ir.requesterid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        WHERE ir.requesterid=%s AND ir.recordstatus=1
        ORDER BY ir.createddatetime DESC LIMIT 50
    """, (empid,))
    iou_types = q("SELECT * FROM ioutypes WHERE recordstatus=1")
    return render_template('employee/iou.html', rows=rows, iou_types=iou_types)


# ─── ATTENDANCE ───────────────────────────────────────────────────────────────
attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/mark', methods=['POST'])
@login_required
def mark():
    empid = current_user.employeeid
    attdate = request.form.get('date', str(datetime.date.today()))
    atttype = request.form.get('attendancetypeid', 1)
    leavetype = request.form.get('leavetypeid') or None
    ismobile = int(request.form.get('ismobile', 0))
    reason = request.form.get('reason', '')
    lat = request.form.get('lat', '')
    lng = request.form.get('lng', '')
    address = request.form.get('address', '')
    try:
        DB.upsert_attendance(empid, attdate, atttype, leavetype, ismobile, current_user.username)
        if ismobile and lat:
            DB.record_mobile_checkin(empid, attdate, reason, lat, lng, address, current_user.username)
        if request.is_json:
            return jsonify({'status': 'ok'})
        flash('Attendance marked.', 'success')
    except Exception as ex:
        if request.is_json:
            return jsonify({'status': 'error', 'message': str(ex)}), 400
        flash(f'Error: {ex}', 'danger')
    return redirect(url_for('employee.my_attendance'))

@attendance_bp.route('/mobile-checkin', methods=['POST'])
@login_required
def mobile_checkin():
    data = request.get_json() or {}
    empid = current_user.employeeid
    attdate = str(datetime.date.today())
    lat = str(data.get('lat', ''))
    lng = str(data.get('lng', ''))
    address = data.get('address', '')
    reason = data.get('reason', 'Mobile check-in')
    att_types = DB.get_attendance_types()
    present_id = next((t['typeid'] for t in att_types if 'Present' in t.get('typename', '')), 1)
    try:
        DB.upsert_attendance(empid, attdate, present_id, None, 1, current_user.username)
        DB.record_mobile_checkin(empid, attdate, reason, lat, lng, address, current_user.username)
        return jsonify({'status': 'ok', 'date': attdate})
    except Exception as ex:
        return jsonify({'status': 'error', 'message': str(ex)}), 400

@attendance_bp.route('/regulation/<int:reqid>/action', methods=['POST'])
@login_required
def regulation_action(reqid):
    action = request.form.get('action', 'approve')
    from app.db import execute
    flag = 1 if action == 'approve' else 2
    execute("""UPDATE attendanceregulationrequest
               SET attendanceregulationflag=%s, modifiedby=%s, modifieddatetime=NOW()
               WHERE attendanceregulationrequestid=%s""",
            (flag, current_user.username, reqid))
    flash(f"Regulation request {action}d.", 'success')
    return redirect(request.referrer or url_for('hr.attendance'))


# ─── LEAVE ────────────────────────────────────────────────────────────────────
leave_bp = Blueprint('leave', __name__)

@leave_bp.route('/request', methods=['POST'])
@login_required
def submit():
    return redirect(url_for('employee.apply_leave'), code=307)


# ─── PAYSLIP ─────────────────────────────────────────────────────────────────
payslip_bp = Blueprint('payslip', __name__)

@payslip_bp.route('/')
@login_required
def index():
    """Payslip list — individual or full time based on role."""
    from app.db import q
    if current_user.is_admin or current_user.is_hr:
        # Show all employees for payslip generation
        employees = DB.get_employees(per_page=500, active_only=True)['rows']
        fiscal_years = DB.get_fiscal_years()
        return render_template('payslip/index.html', employees=employees,
                               fiscal_years=fiscal_years)
    else:
        # Employee sees own payslips
        empid = current_user.employeeid
        payments = DB.get_claim_payments(employeeid=empid, per_page=100)
        return render_template('payslip/my_payslips.html', result=payments)

@payslip_bp.route('/view/<int:empid>')
@login_required
def view(empid):
    """View individual payslip."""
    from app.db import q
    # Access control
    if not (current_user.is_admin or current_user.is_hr or current_user.employeeid == empid):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))

    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)

    emp = DB.get_employee_full_profile(empid)
    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('payslip.index'))

    salary_structure = DB.get_salary_structure(emp['gradeid']) if emp.get('gradeid') else []

    # Get payments for this month
    try:
        payments = q("""
            SELECT cp.*
            FROM claimpayment cp
            WHERE cp.paidtoid = %s
            AND MONTH(cp.paymentdate) = %s AND YEAR(cp.paymentdate) = %s
            AND cp.recordstatus = 1
            ORDER BY cp.paymentdate
        """, (empid, month, year))
    except:
        payments = []

    # Get claim vouchers for this period
    try:
        vouchers = q("""
            SELECT cv.*
            FROM claimvoucher cv
            WHERE cv.requestedbyid = %s
            AND MONTH(cv.voucherdate) = %s AND YEAR(cv.voucherdate) = %s
            AND cv.recordstatus = 1
        """, (empid, month, year))
    except:
        vouchers = []

    return render_template('payslip/view.html', emp=emp,
                           salary_structure=salary_structure,
                           payments=payments, vouchers=vouchers,
                           month=month, year=year)

@payslip_bp.route('/fulltime')
@login_required
def fulltime():
    """Full time payslip — all employees for a given month."""
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)

    employees = q("""
        SELECT e.employeeid, e.employeenumber,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               g.typename as grade, d.departmentname,
               bu.businessunitname as vertical
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN gradetypes g ON e.gradeid = g.typeid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        LEFT JOIN businessunit bu ON e.businessunit = bu.businessunitid
        WHERE e.activeflag = 1 AND e.recordstatus = 1
        ORDER BY c.firstname
    """)

    return render_template('payslip/fulltime.html', employees=employees,
                           month=month, year=year)


# ─── CTC ─────────────────────────────────────────────────────────────────────
ctc_bp = Blueprint('ctc', __name__)

@ctc_bp.route('/')
@login_required
def index():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    employees = DB.get_employees(per_page=500, active_only=True)['rows']
    return render_template('ctc/index.html', employees=employees)

@ctc_bp.route('/view/<int:empid>')
@login_required
def view(empid):
    if not (current_user.is_admin or current_user.is_hr or current_user.employeeid == empid):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    emp = DB.get_employee_full_profile(empid)
    salary_structure = DB.get_salary_structure(emp['gradeid']) if emp and emp.get('gradeid') else []
    # Get CTC details from claim voucher
    try:
        ctc_details = q("""
            SELECT cd.*
            FROM claimctcdetails cd
            JOIN claimvoucher cv ON cd.claimvoucherid = cv.claimvoucherrequestid
            WHERE cv.requestedbyid = %s AND cv.recordstatus=1
            ORDER BY cd.ctcmonth DESC LIMIT 24
        """, (empid,))
    except:
        ctc_details = []
    return render_template('ctc/view.html', emp=emp,
                           salary_structure=salary_structure, ctc_details=ctc_details)

@ctc_bp.route('/summary')
@login_required
def summary():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    dept = request.args.get('dept')
    vertical = request.args.get('vertical')
    employees = DB.get_employees(per_page=500, active_only=True,
                                  dept=dept, vertical=vertical)['rows']
    depts = DB.get_departments()
    verticals = DB.get_verticals()
    return render_template('ctc/summary.html', employees=employees,
                           depts=depts, verticals=verticals)

@ctc_bp.route('/increment')
@login_required
def increment():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    grades = DB.get_grades()
    return render_template('ctc/increment.html', grades=grades)


# ─── SEPARATION ───────────────────────────────────────────────────────────────
separation_bp = Blueprint('separation', __name__)

@separation_bp.route('/')
@login_required
def index():
    from app.db import q
    empid = None if (current_user.is_admin or current_user.is_hr) else current_user.employeeid
    where = "e.recordstatus=1"
    args = []
    if empid:
        where += " AND rrl.employeeid=%s"; args.append(empid)
    rows = q(f"""
        SELECT rrl.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber
        FROM hrreceiveresignletter rrl
        JOIN employees e ON rrl.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        WHERE {where}
        ORDER BY rrl.createddatetime DESC LIMIT 100
    """, args)
    return render_template('separation/index.html', rows=rows)

@separation_bp.route('/receive-resign')
@login_required
def receive_resign():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("""
        SELECT rrl.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname
        FROM hrreceiveresignletter rrl
        JOIN employees e ON rrl.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        WHERE rrl.recordstatus=1
        ORDER BY rrl.createddatetime DESC
    """)
    employees = DB.get_employees(per_page=500, active_only=True)['rows']
    return render_template('separation/receive_resign.html', rows=rows, employees=employees)

@separation_bp.route('/accept-resign')
@login_required
def accept_resign():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("""
        SELECT arl.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber
        FROM hracceptresignletter arl
        JOIN hrreceiveresignletter rrl ON arl.receiveresignletterid = rrl.receiveresignletterid
        JOIN employees e ON rrl.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        WHERE arl.recordstatus=1
        ORDER BY arl.createddatetime DESC
    """)
    return render_template('separation/accept_resign.html', rows=rows)

@separation_bp.route('/noc-departments')
@login_required
def noc_departments():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("""
        SELECT hn.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d2.departmentname as clearance_dept
        FROM hrnocfromdepts hn
        JOIN hrreceiveresignletter rrl ON hn.receiveresignletterid = rrl.receiveresignletterid
        JOIN employees e ON rrl.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d2 ON hn.departmentid = d2.departmentid
        WHERE hn.recordstatus=1
        ORDER BY hn.createddatetime DESC
    """)
    depts = DB.get_departments()
    return render_template('separation/noc.html', rows=rows, depts=depts)

@separation_bp.route('/experience-letter')
@login_required
def experience_letter():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("""
        SELECT el.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, e.doj, e.dot,
               dt.typename as designation
        FROM hrexperienceletter el
        JOIN employees e ON el.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN designationtypes dt ON e.designationid = dt.typeid
        WHERE el.recordstatus=1
        ORDER BY el.createddatetime DESC
    """)
    return render_template('separation/experience_letter.html', rows=rows)

@separation_bp.route('/no-due-certificate')
@login_required
def no_due():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("""
        SELECT ndc.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               NULL as employeenumber
        FROM noduecertificate ndc
        JOIN contact c ON ndc.contactpersonid = c.contactid
        WHERE ndc.recordstatus=1
        ORDER BY ndc.createddatetime DESC
    """)
    return render_template('separation/no_due.html', rows=rows)


# ─── IOU ─────────────────────────────────────────────────────────────────────
iou_bp = Blueprint('iou', __name__)

@iou_bp.route('/')
@login_required
def index():
    from app.db import q
    empid = None if (current_user.is_admin or current_user.is_hr) else current_user.employeeid
    where = "ir.recordstatus=1"
    args = []
    if empid:
        where += " AND ir.requesterid=%s"; args.append(empid)
    rows = q(f"""
        SELECT ir.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber,
               it.typename as ioutype
        FROM iourequest ir
        JOIN employees e ON ir.requesterid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN ioutypes it ON ir.ioutypeid = it.typeid
        WHERE {where}
        ORDER BY ir.createddatetime DESC LIMIT 200
    """, args)
    iou_types = q("SELECT * FROM ioutypes WHERE recordstatus=1")
    employees = DB.get_employees(per_page=500, active_only=True)['rows'] if (current_user.is_admin or current_user.is_hr) else []
    return render_template('iou/index.html', rows=rows, iou_types=iou_types, employees=employees)

@iou_bp.route('/submit', methods=['POST'])
@login_required
def submit():
    from app.db import execute
    empid = current_user.employeeid
    ioutypeid = request.form.get('ioutypeid')
    amount = request.form.get('amount', 0)
    reason = request.form.get('reason', '')
    iou_num = f"IOU{empid}{datetime.date.today().strftime('%Y%m%d%H%M%S')}"
    try:
        execute("""
            INSERT INTO iourequest
            (iounumber, requesterid, ioutypeid, requestdate, advanceamount,
             otherreason, iourequestflag, createdby, createddatetime,
             modifiedby, modifieddatetime, recordstatus)
            VALUES (%s, %s, %s, CURDATE(), %s, %s, 0, %s, NOW(), %s, NOW(), 1)
        """, (iou_num, empid, ioutypeid, amount, reason,
              current_user.username, current_user.username))
        flash('IOU request submitted.', 'success')
    except Exception as ex:
        flash(f'Error: {ex}', 'danger')
    return redirect(url_for('iou.index'))

@iou_bp.route('/<int:iouid>/approve', methods=['POST'])
@login_required
def approve(iouid):
    if not (current_user.is_admin or current_user.is_hr):
        return jsonify({'status': 'error'}), 403
    from app.db import execute
    action = request.form.get('action', 'approve')
    flag = 1 if action == 'approve' else 2
    execute("""UPDATE iourequest SET iourequestflag=%s,
               modifiedby=%s, modifieddatetime=NOW()
               WHERE iouid=%s""",
            (flag, current_user.username, iouid))
    flash(f"IOU {action}d.", 'success')
    return redirect(url_for('iou.index'))


# ─── FOOD COUPON ──────────────────────────────────────────────────────────────
foodcoupon_bp = Blueprint('foodcoupon', __name__)

@foodcoupon_bp.route('/')
@login_required
def index():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    rows = q("""
        SELECT fc.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname
        FROM foodcoupan fc
        JOIN employees e ON fc.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        WHERE MONTH(fc.coupanreceivedate)=%s AND YEAR(fc.coupanreceivedate)=%s
        AND fc.recordstatus=1
        ORDER BY empname
    """, (month, year))
    return render_template('foodcoupon/index.html', rows=rows, month=month, year=year)


# ─── NPR (PART TIME) ─────────────────────────────────────────────────────────
npr_bp = Blueprint('npr', __name__)

@npr_bp.route('/')
@login_required
def index():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    employees = q("""
        SELECT e.employeeid, e.employeenumber,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.parttimeempsalary, d.departmentname,
               et.typename as emptype
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        JOIN employeetypes et ON e.employeetypeid = et.typeid
        WHERE et.typename LIKE %s AND e.recordstatus=1
        ORDER BY empname
    """, ('%Part%',))
    return render_template('npr/index.html', employees=employees)

@npr_bp.route('/attendance')
@login_required
def attendance():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    rows = q("""
        SELECT da.*, CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber
        FROM dailyattendanceparttime da
        JOIN employees e ON da.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        WHERE MONTH(da.attendancedate)=%s AND YEAR(da.attendancedate)=%s
        AND da.recordstatus=1
        ORDER BY empname, da.attendancedate
    """, (month, year))
    return render_template('npr/attendance.html', rows=rows, month=month, year=year)

@npr_bp.route('/payslip')
@login_required
def payslip():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    # Count attendance days for part-time employees
    rows = q("""
        SELECT e.employeeid, e.employeenumber, e.parttimeempsalary,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               COUNT(da.attendanceid) as days_present,
               (COUNT(da.attendanceid) * e.parttimeempsalary) as total_salary
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        JOIN employeetypes et ON e.employeetypeid = et.typeid
        LEFT JOIN dailyattendanceparttime da ON e.employeeid = da.employeeid
            AND MONTH(da.attendancedate)=%s AND YEAR(da.attendancedate)=%s
            AND da.recordstatus=1
        WHERE et.typename LIKE %s AND e.recordstatus=1
        GROUP BY e.employeeid
        ORDER BY empname
    """, (month, year, '%Part%'))
    return render_template('npr/payslip.html', rows=rows, month=month, year=year)


# ─── REPORTS ─────────────────────────────────────────────────────────────────
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
@login_required
def index():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    return render_template('reports/index.html')

@reports_bp.route('/attendance')
@login_required
def attendance_report():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    dept = request.args.get('dept')
    vertical = request.args.get('vertical')

    base_args = [month, year]
    extra_where = ""
    if dept:
        extra_where += " AND e.departmentid=%s"
        base_args.append(dept)
    if vertical:
        extra_where += " AND e.businessunit=%s"
        base_args.append(vertical)

    rows = q("""
        SELECT e.employeeid, e.employeenumber,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               d.departmentname,
               SUM(CASE WHEN at.typename LIKE %s THEN 1 ELSE 0 END) as present_days,
               SUM(CASE WHEN at.typename LIKE %s THEN 1 ELSE 0 END) as leave_days,
               SUM(CASE WHEN at.typename LIKE %s THEN 1 ELSE 0 END) as absent_days,
               SUM(CASE WHEN da.ismobile=1 THEN 1 ELSE 0 END) as mobile_days,
               COUNT(da.attendanceid) as total_marked
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        LEFT JOIN dailyattendance da ON e.employeeid=da.employeeid
            AND MONTH(da.attendancedate)=%s AND YEAR(da.attendancedate)=%s
            AND da.recordstatus=1
        LEFT JOIN attendancetypes at ON da.attendancetypeid=at.typeid
        WHERE e.recordstatus=1 AND e.activeflag=1""" + extra_where + """
        GROUP BY e.employeeid
        ORDER BY empname
    """, ['%Present%', '%Leave%', '%Absent%'] + base_args)

    depts = DB.get_departments()
    verticals = DB.get_verticals()
    return render_template('reports/attendance.html', rows=rows,
                           month=month, year=year, depts=depts, verticals=verticals)

@reports_bp.route('/employee-consolidated')
@login_required
def employee_consolidated():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    empid = request.args.get('empid', type=int)
    emp = None
    leave_balance = []
    att_summary = []
    payments = []
    loans = []
    if empid:
        emp = DB.get_employee_full_profile(empid)
        leave_balance = DB.get_leave_balance(empid)
        att_summary = DB.get_attendance_summary_for_employee(empid)
        payments = DB.get_claim_payments(employeeid=empid, per_page=50)['rows']
        loans = DB.get_employee_loans(empid)
    employees = DB.get_employees(per_page=500, active_only=True)['rows']
    return render_template('reports/employee_consolidated.html',
                           emp=emp, employees=employees,
                           leave_balance=leave_balance, att_summary=att_summary,
                           payments=payments, loans=loans, empid=empid)

@reports_bp.route('/salary-payment')
@login_required
def salary_payment():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    rows = q("""
        SELECT cp.*,
               CONCAT(c1.firstname,' ',IFNULL(c1.lastname,'')) as paidto_name,
               e1.employeenumber,
               d.departmentname,
               pd.paymentdesc as pay_type
        FROM claimpayment cp
        JOIN employees e1 ON cp.paidtoid = e1.employeeid
        JOIN contact c1 ON e1.contactid = c1.contactid
        LEFT JOIN departments d ON e1.departmentid = d.departmentid
        LEFT JOIN paymentdesc pd ON cp.paymentdescid = pd.paymentdescid
        WHERE MONTH(cp.paymentdate)=%s AND YEAR(cp.paymentdate)=%s
        AND cp.recordstatus=1
        ORDER BY paidto_name
    """, (month, year))
    return render_template('reports/salary_payment.html', rows=rows, month=month, year=year)

@reports_bp.route('/bonus-payment')
@login_required
def bonus_payment():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    year = int(request.args.get('year') or datetime.date.today().year)
    rows = q("""
        SELECT b.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname
        FROM bonus b
        JOIN employees e ON b.employeeid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        WHERE YEAR(b.bonusdate)=%s AND b.recordstatus=1
        ORDER BY empname
    """, (year,))
    return render_template('reports/bonus_payment.html', rows=rows, year=year)

@reports_bp.route('/pf-challan')
@login_required
def pf_challan():
    if not (current_user.is_admin or current_user.is_hr):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    month = int(request.args.get('month') or datetime.date.today().month)
    year = int(request.args.get('year') or datetime.date.today().year)
    # PF is calculated from salary — 12% of basic
    rows = q("""
        SELECT e.employeeid, e.employeenumber,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               g.typename as grade, d.departmentname
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN gradetypes g ON e.gradeid = g.typeid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        WHERE e.activeflag=1 AND e.recordstatus=1
        ORDER BY empname
    """)
    return render_template('reports/pf_challan.html', rows=rows, month=month, year=year)


# ─── PAYROLL ─────────────────────────────────────────────────────────────────
payroll_bp = Blueprint('payroll', __name__)

@payroll_bp.route('/')
@login_required
def index():
    if current_user.is_admin or current_user.is_hr:
        result = DB.get_claim_vouchers(per_page=50)
        return render_template('payroll/index.html', result=result)
    else:
        empid = current_user.employeeid
        result = DB.get_claim_payments(employeeid=empid, per_page=50)
        return render_template('payroll/my_payroll.html', result=result)

@payroll_bp.route('/employee/<int:empid>')
@login_required
def employee_payroll(empid):
    if not (current_user.is_admin or current_user.is_hr or current_user.employeeid == empid):
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    result = DB.get_claim_payments(employeeid=empid, per_page=100)
    emp = DB.get_employee_full_profile(empid)
    salary = DB.get_salary_structure(emp['gradeid']) if emp and emp.get('gradeid') else []
    return render_template('payroll/employee_payroll.html',
                           result=result, salary=salary, emp=emp)


# ─── RECRUITMENT ─────────────────────────────────────────────────────────────
recruitment_bp = Blueprint('recruitment', __name__)

@recruitment_bp.route('/')
@login_required
def index():
    result = DB.get_recruitment_requests()
    return render_template('recruitment/index.html', result=result)

@recruitment_bp.route('/candidates')
@login_required
def candidates():
    from app.db import q
    rrid = request.args.get('rrid', type=int)
    candidates = DB.get_candidates(rrid)
    requests = DB.get_recruitment_requests()['rows']
    return render_template('recruitment/candidates.html',
                           candidates=candidates, requests=requests, rrid=rrid)

@recruitment_bp.route('/offer-letters')
@login_required
def offer_letters():
    from app.db import q
    rows = q("""
        SELECT ho.*,
               CONCAT(hc.firstname,' ',IFNULL(hc.lastname,'')) as empname,
               NULL as employeenumber
        FROM hrofferletter ho
        JOIN hrcandidate hc ON ho.candidateid = hc.hrcandidateid
        WHERE ho.recordstatus=1
        ORDER BY ho.createddatetime DESC
    """)
    return render_template('recruitment/offer_letters.html', rows=rows)

@recruitment_bp.route('/appointment-letters')
@login_required
def appointment_letters():
    from app.db import q
    rows = q("""
        SELECT ha.*,
               CONCAT(hc.firstname,' ',IFNULL(hc.lastname,'')) as empname,
               NULL as employeenumber
        FROM hrappointmentletter ha
        JOIN hrcandidate hc ON ha.candidateid = hc.hrcandidateid
        WHERE ha.recordstatus=1
        ORDER BY ha.createddatetime DESC
    """)
    return render_template('recruitment/appointment_letters.html', rows=rows)

@recruitment_bp.route('/consultancy')
@login_required
def consultancy():
    from app.db import q
    rows = q("""
        SELECT hc.*,
               CONCAT(cand.firstname,' ',IFNULL(cand.lastname,'')) as empname,
               hc.rolename, hc.remuneration
        FROM hrconsultancy hc
        JOIN hrcandidate cand ON hc.hrcandidateid = cand.hrcandidateid
        WHERE hc.recordstatus=1
        ORDER BY hc.createddatetime DESC
    """)
    return render_template('recruitment/consultancy.html', rows=rows)


# ─── GRIEVANCE ───────────────────────────────────────────────────────────────
grievance_bp = Blueprint('grievance', __name__)

@grievance_bp.route('/')
@login_required
def index():
    empid = current_user.employeeid if current_user.is_employee else None
    result = DB.get_grievances(employeeid=empid)
    return render_template('grievance/index.html', result=result)


# ─── KPI ─────────────────────────────────────────────────────────────────────
kpi_bp = Blueprint('kpi', __name__)

@kpi_bp.route('/')
@login_required
def index():
    empid = None if (current_user.is_admin or current_user.is_hr) else current_user.employeeid
    fiscal = DB.get_current_fiscal_year()
    fy = request.args.get('fy', fiscal['fiscalvalue'] if fiscal else '')
    targets = DB.get_kpi_targets(employeeid=empid, fiscalyear=fy)
    fiscal_years = DB.get_fiscal_years()
    return render_template('kpi/index.html', targets=targets,
                           fiscal_years=fiscal_years, fy=fy)


# ─── TRAVEL ──────────────────────────────────────────────────────────────────
travel_bp = Blueprint('travel', __name__)

@travel_bp.route('/')
@login_required
def index():
    from app.db import q
    empid = None if (current_user.is_admin or current_user.is_hr) else current_user.employeeid
    where = "tr.recordstatus=1"
    args = []
    if empid:
        where += " AND tr.requesterid=%s"; args.append(empid)
    rows = q(f"""
        SELECT tr.*,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as requester_name,
               e.employeenumber
        FROM travelrequest tr
        JOIN employees e ON tr.requesterid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        WHERE {where}
        ORDER BY tr.createddatetime DESC LIMIT 100
    """, args)
    return render_template('travel/index.html', rows=rows)


# ─── ADMIN ATTRIBUTES ─────────────────────────────────────────────────────────
admin_attr_bp = Blueprint('admin_attr', __name__)

@admin_attr_bp.route('/grades')
@login_required
def grades():
    from app.db import q
    rows = q("SELECT * FROM gradetypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/grades.html', rows=rows, title='Grade Types')

@admin_attr_bp.route('/salary-types')
@login_required
def salary_types():
    from app.db import q
    rows = q("""
        SELECT gst.*, gt.typename as grade_name, gst.amount, gst.amounttype, gst.frequency
        FROM gradesalarytype gst
        LEFT JOIN gradetypes gt ON gst.gradetypeid = gt.typeid
        WHERE gst.recordstatus=1
        ORDER BY gt.typename
    """)
    return render_template('admin_attr/simple_list.html', rows=rows, title='Salary Types', cols=['grade_name', 'amount', 'amounttype', 'frequency'])

@admin_attr_bp.route('/leave-types')
@login_required
def leave_types():
    from app.db import q
    rows = q("SELECT * FROM leavetypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/leave_types.html', rows=rows, title='Leave Types')

@admin_attr_bp.route('/attendance-types')
@login_required
def attendance_types():
    from app.db import q
    rows = q("SELECT * FROM attendancetypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/simple_list.html', rows=rows, title='Attendance Types', cols=['typename', 'typecolour'])

@admin_attr_bp.route('/departments')
@login_required
def departments():
    from app.db import q
    rows = q("""
        SELECT d.*, bu.businessunitname as vertical
        FROM departments d
        LEFT JOIN businessunit bu ON d.businessunitid = bu.businessunitid
        WHERE d.recordstatus=1 ORDER BY d.departmentname
    """)
    return render_template('admin_attr/departments.html', rows=rows)

@admin_attr_bp.route('/designations')
@login_required
def designations():
    from app.db import q
    rows = q("SELECT * FROM designationtypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/simple_list.html', rows=rows, title='Designations', cols=['typename'])

@admin_attr_bp.route('/branches')
@login_required
def branches():
    from app.db import q
    rows = q("SELECT * FROM branches WHERE recordstatus=1 ORDER BY branchesname")
    return render_template('admin_attr/branches.html', rows=rows)

@admin_attr_bp.route('/business-units')
@login_required
def business_units():
    rows = DB.get_verticals()
    return render_template('admin_attr/simple_list.html', rows=rows, title='Business Units / Verticals', cols=['businessunitname', 'businessunitcode'])

@admin_attr_bp.route('/fiscal-years')
@login_required
def fiscal_years():
    rows = DB.get_fiscal_years()
    return render_template('admin_attr/fiscal_years.html', rows=rows)

@admin_attr_bp.route('/employee-types')
@login_required
def employee_types():
    from app.db import q
    rows = q("SELECT * FROM employeetypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/simple_list.html', rows=rows, title='Employee Types', cols=['typename', 'prefix'])

@admin_attr_bp.route('/investment-types')
@login_required
def investment_types():
    from app.db import q
    rows = q("SELECT * FROM investmenttypes WHERE recordstatus=1 ORDER BY investmentname")
    return render_template('admin_attr/simple_list.html', rows=rows, title='Investment Types', cols=['investmentname', 'investmentdesc'])

@admin_attr_bp.route('/iou-types')
@login_required
def iou_types():
    from app.db import q
    rows = q("SELECT * FROM ioutypes WHERE recordstatus=1 ORDER BY typename")
    return render_template('admin_attr/simple_list.html', rows=rows, title='IOU Types', cols=['typename'])

@admin_attr_bp.route('/holidays')
@login_required
def holidays():
    year = int(request.args.get('year') or datetime.date.today().year)
    rows = DB.get_holidays(year=year)
    years = list(range(2010, datetime.date.today().year + 3))
    return render_template('admin_attr/holidays.html', rows=rows, year=year, years=years)


# ─── USER MANAGEMENT ─────────────────────────────────────────────────────────
user_mgmt_bp = Blueprint('user_mgmt', __name__)

@user_mgmt_bp.route('/')
@login_required
def index():
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    page = int(request.args.get('page', 1))
    search = request.args.get('q', '')
    per_page = 50
    offset = (page - 1) * per_page
    where = "u.recordstatus=1"
    args = []
    if search:
        where += " AND (u.username LIKE %s OR c.firstname LIKE %s)"
        s = f"%{search}%"
        args += [s, s]
    total = q(f"SELECT COUNT(*) as cnt FROM users u LEFT JOIN employees e ON u.userid=e.userid LEFT JOIN contact c ON e.contactid=c.contactid WHERE {where}", args, one=True)['cnt']
    rows = q(f"""
        SELECT u.userid, u.username, u.activestatus, u.mobileaccess,
               u.mobileattendanceflag, u.createddatetime,
               ut.typename as usertype, r.rolename,
               CONCAT(IFNULL(c.firstname,''),' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber
        FROM users u
        JOIN usertypes ut ON u.usertypeid = ut.typeid
        JOIN roles r ON u.roleid = r.roleid
        LEFT JOIN employees e ON u.userid = e.userid
        LEFT JOIN contact c ON e.contactid = c.contactid
        WHERE {where}
        ORDER BY u.createddatetime DESC
        LIMIT %s OFFSET %s
    """, args + [per_page, offset])
    pages = (total + per_page - 1) // per_page
    return render_template('user_mgmt/index.html', rows=rows, total=total,
                           page=page, pages=pages, search=search)

@user_mgmt_bp.route('/reset-password/<int:userid>', methods=['POST'])
@login_required
def reset_password(userid):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import execute
    import hashlib
    new_pwd = request.form.get('new_password', 'Procam@2024')
    hashed = hashlib.md5(new_pwd.encode()).hexdigest()
    execute("UPDATE users SET pwd=%s, modifiedby=%s, modifieddatetime=NOW() WHERE userid=%s",
            (hashed, current_user.username, userid))
    flash(f'Password reset successfully.', 'success')
    return redirect(url_for('user_mgmt.index'))

@user_mgmt_bp.route('/toggle-mobile/<int:userid>', methods=['POST'])
@login_required
def toggle_mobile(userid):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import execute, q
    user = q("SELECT mobileattendanceflag FROM users WHERE userid=%s", (userid,), one=True)
    new_flag = 0 if user['mobileattendanceflag'] else 1
    execute("UPDATE users SET mobileattendanceflag=%s WHERE userid=%s", (new_flag, userid))
    flash(f"Mobile attendance {'enabled' if new_flag else 'disabled'}.", 'success')
    return redirect(url_for('user_mgmt.index'))

@user_mgmt_bp.route('/roles')
@login_required
def roles():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    from app.db import q
    rows = q("SELECT * FROM roles WHERE recordstatus=1 ORDER BY rolename")
    return render_template('user_mgmt/roles.html', rows=rows)


# ─── API ─────────────────────────────────────────────────────────────────────
api_bp = Blueprint('api', __name__)

@api_bp.route('/me')
@login_required
def me():
    return jsonify({
        'userid': current_user.userid,
        'employeeid': current_user.employeeid,
        'name': current_user.fullname,
        'username': current_user.username,
        'role': current_user.rolename,
        'usertype': current_user.usertype,
        'mobile_attendance': bool(current_user.mobileattendanceflag),
    })

@api_bp.route('/attendance/today')
@login_required
def attendance_today():
    from app.db import q
    empid = current_user.employeeid
    att = q("""
        SELECT da.*, at.typename, at.typecolour, lt.typename as leavetype
        FROM dailyattendance da
        JOIN attendancetypes at ON da.attendancetypeid=at.typeid
        LEFT JOIN leavetypes lt ON da.leavetypeid=lt.typeid
        WHERE da.employeeid=%s AND da.attendancedate=CURDATE() AND da.recordstatus=1
    """, (empid,), one=True)
    return jsonify({'status': 'ok', 'attendance': att,
                   'date': str(datetime.date.today())})

@api_bp.route('/attendance/checkin', methods=['POST'])
@login_required
def checkin():
    data = request.get_json() or {}
    empid = current_user.employeeid
    attdate = str(datetime.date.today())
    lat = str(data.get('lat', ''))
    lng = str(data.get('lng', ''))
    address = data.get('address', '')
    reason = data.get('reason', 'Mobile check-in')
    att_types = DB.get_attendance_types()
    present_id = next((t['typeid'] for t in att_types if 'Present' in t.get('typename', '')), 1)
    try:
        DB.upsert_attendance(empid, attdate, present_id, None, 1, current_user.username)
        DB.record_mobile_checkin(empid, attdate, reason, lat, lng, address, current_user.username)
        return jsonify({'status': 'ok', 'message': 'Checked in.', 'date': attdate})
    except Exception as ex:
        return jsonify({'status': 'error', 'message': str(ex)}), 400

@api_bp.route('/leave/balance')
@login_required
def leave_balance():
    balance = DB.get_leave_balance(current_user.employeeid)
    return jsonify({'status': 'ok', 'balance': balance})

@api_bp.route('/attendance/month')
@login_required
def attendance_month():
    empid = current_user.employeeid
    year = int(request.args.get('year') or datetime.date.today().year)
    month = int(request.args.get('month') or datetime.date.today().month)
    records = DB.get_attendance_for_month(empid, year, month)
    return jsonify({'status': 'ok', 'records': [dict(r) for r in records]})

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    if current_user.is_admin or current_user.is_hr:
        stats = DB.get_admin_dashboard_stats()
        return jsonify({'status': 'ok', 'stats': stats})
    return jsonify({'status': 'error', 'message': 'Access denied'}), 403