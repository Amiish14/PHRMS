from app import mysql
import MySQLdb.cursors


def get_db():
    return mysql.connection


def q(sql, args=(), one=False):
    cur = get_db().cursor(MySQLdb.cursors.DictCursor)
    cur.execute(sql, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute(sql, args=()):
    cur = get_db().cursor()
    cur.execute(sql, args)
    get_db().commit()
    lid = cur.lastrowid
    cur.close()
    return lid


# ─── AUTH ────────────────────────────────────────────────────────────────────

def get_user_by_username(username):
    return q("""
        SELECT u.userid, u.username, u.pwd, u.usertypeid, u.roleid,
               u.activestatus, u.mobileaccess, u.mobileattendanceflag,
               u.lockcount, u.passwordage,
               ut.typename as usertype,
               r.rolename,
               e.employeeid, e.employeenumber, e.gradeid, e.branchid,
               e.departmentid, e.designationid, e.activeflag,
               e.businessunit,
               c.firstname, c.lastname
        FROM users u
        JOIN usertypes ut ON u.usertypeid = ut.typeid
        JOIN roles r ON u.roleid = r.roleid
        LEFT JOIN employees e ON u.userid = e.userid
        LEFT JOIN contact c ON e.contactid = c.contactid
        WHERE u.username = %s AND u.recordstatus = 1
    """, (username,), one=True)


def get_user_by_id(userid):
    return q("""
        SELECT u.userid, u.username, u.usertypeid, u.roleid,
               u.activestatus, u.mobileaccess, u.mobileattendanceflag,
               ut.typename as usertype, r.rolename,
               e.employeeid, e.employeenumber, e.gradeid, e.branchid,
               e.departmentid, e.designationid, e.activeflag,
               e.businessunit, e.doj, e.dot, e.gender,
               c.firstname, c.lastname,
               d.departmentname,
               dt.typename as designation,
               g.typename as grade,
               b.branchesname
        FROM users u
        JOIN usertypes ut ON u.usertypeid = ut.typeid
        JOIN roles r ON u.roleid = r.roleid
        LEFT JOIN employees e ON u.userid = e.userid
        LEFT JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        LEFT JOIN designationtypes dt ON e.designationid = dt.typeid
        LEFT JOIN gradetypes g ON e.gradeid = g.typeid
        LEFT JOIN branches b ON e.branchid = b.branchid
        WHERE u.userid = %s AND u.recordstatus = 1
    """, (userid,), one=True)


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

def get_admin_dashboard_stats():
    stats = {}
    try:
        stats['total_employees'] = q(
            "SELECT COUNT(*) as cnt FROM employees WHERE activeflag=1 AND recordstatus=1",
            one=True)['cnt']
    except: stats['total_employees'] = 0

    try:
        # Use last date with attendance records (data ends Oct 2022)
        last_att_date = q(
            "SELECT MAX(attendancedate) as ld FROM dailyattendance WHERE recordstatus=1",
            one=True)
        last_date = last_att_date['ld'] if last_att_date and last_att_date['ld'] else 'CURDATE()'
        stats['last_attendance_date'] = str(last_date)
        stats['present_today'] = q(
            "SELECT COUNT(*) as cnt FROM dailyattendance da "
            "JOIN attendancetypes at ON da.attendancetypeid=at.typeid "
            "WHERE da.attendancedate=%s AND da.recordstatus=1 "
            "AND at.typename LIKE '%Present%'", (last_date,), one=True)['cnt']
    except: stats['present_today'] = 0; stats['last_attendance_date'] = ''

    try:
        stats['on_leave_today'] = q(
            "SELECT COUNT(*) as cnt FROM dailyattendance da "
            "JOIN attendancetypes at ON da.attendancetypeid=at.typeid "
            "WHERE da.attendancedate=%s AND da.recordstatus=1 "
            "AND (at.typename LIKE '%Leave%' OR at.typename LIKE '%Absent%')",
            (last_date,), one=True)['cnt']
    except: stats['on_leave_today'] = 0

    try:
        stats['pending_leave_approvals'] = q(
            "SELECT COUNT(*) as cnt FROM leaverequest "
            "WHERE employeeleaveflag=0 AND recordstatus=1", one=True)['cnt']
    except: stats['pending_leave_approvals'] = 0

    try:
        stats['pending_attendance_reg'] = q(
            "SELECT COUNT(*) as cnt FROM attendanceregulationrequest "
            "WHERE attendanceregulationflag=0 AND recordstatus=1", one=True)['cnt']
    except: stats['pending_attendance_reg'] = 0

    try:
        stats['mobile_checkins_today'] = q(
            "SELECT COUNT(*) as cnt FROM mobileattendancereason "
            "WHERE attendancedate=CURDATE() AND recordstatus=1", one=True)['cnt']
    except: stats['mobile_checkins_today'] = 0

    try:
        stats['new_joiners_month'] = q(
            "SELECT COUNT(*) as cnt FROM employees "
            "WHERE MONTH(doj)=MONTH(CURDATE()) AND YEAR(doj)=YEAR(CURDATE()) "
            "AND recordstatus=1", one=True)['cnt']
    except: stats['new_joiners_month'] = 0

    try:
        stats['pending_grievances'] = q(
            "SELECT COUNT(*) as cnt FROM grievance "
            "WHERE recordstatus=1 AND statusid NOT IN (2,3)", one=True)['cnt']
    except: stats['pending_grievances'] = 0

    return stats


def get_headcount_by_vertical():
    try:
        return q("""
            SELECT bu.businessunitname as vertical, COUNT(e.employeeid) as cnt
            FROM employees e
            JOIN businessunit bu ON e.businessunit = bu.businessunitid
            WHERE e.activeflag=1 AND e.recordstatus=1
            GROUP BY bu.businessunitid, bu.businessunitname
            ORDER BY cnt DESC
        """)
    except: return []


def get_attendance_trend_30days():
    try:
        return q("""
            SELECT da.attendancedate, at.typename, COUNT(*) as cnt
            FROM dailyattendance da
            JOIN attendancetypes at ON da.attendancetypeid = at.typeid
            WHERE da.attendancedate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            AND da.recordstatus=1
            GROUP BY da.attendancedate, at.typeid
            ORDER BY da.attendancedate
        """)
    except: return []


def get_leave_summary_current_month():
    try:
        return q("""
            SELECT lt.typename, COUNT(*) as cnt
            FROM leaverequest lr
            JOIN leavetypes lt ON lr.leavetypeid = lt.typeid
            WHERE YEAR(lr.startdate)=(SELECT YEAR(MAX(startdate)) FROM leaverequest WHERE recordstatus=1)
            AND MONTH(lr.startdate)=(SELECT MONTH(MAX(startdate)) FROM leaverequest WHERE recordstatus=1)
            AND lr.recordstatus=1
            GROUP BY lt.typeid, lt.typename
        """)
    except: return []


def get_todays_mobile_checkins():
    try:
        return q("""
            SELECT m.mobileattendancereasonid, m.employeeid,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber, m.attendancedate,
                   m.resaon, m.lat, m.lng, m.address,
                   m.createddatetime
            FROM mobileattendancereason m
            JOIN employees e ON m.employeeid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            WHERE m.attendancedate = CURDATE() AND m.recordstatus=1
            ORDER BY m.createddatetime DESC
            LIMIT 50
        """)
    except: return []


def get_birthdays_this_week():
    try:
        return q("""
            SELECT CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber, e.celebratedob, e.dob,
                   d.departmentname, b.branchesname
            FROM employees e
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN departments d ON e.departmentid = d.departmentid
            LEFT JOIN branches b ON e.branchid = b.branchid
            WHERE e.activeflag=1 AND e.recordstatus=1
            AND (
                (MONTH(e.celebratedob)=MONTH(CURDATE())
                 AND DAY(e.celebratedob) BETWEEN DAY(CURDATE())
                 AND DAY(DATE_ADD(CURDATE(), INTERVAL 7 DAY)))
                OR
                (MONTH(e.dob)=MONTH(CURDATE())
                 AND DAY(e.dob) BETWEEN DAY(CURDATE())
                 AND DAY(DATE_ADD(CURDATE(), INTERVAL 7 DAY)))
            )
            LIMIT 10
        """)
    except: return []


def get_recent_joiners(limit=10):
    try:
        return q("""
            SELECT CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber, e.doj,
                   dt.typename as designation,
                   d.departmentname,
                   bu.businessunitname as vertical
            FROM employees e
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN designationtypes dt ON e.designationid = dt.typeid
            LEFT JOIN departments d ON e.departmentid = d.departmentid
            LEFT JOIN businessunit bu ON e.businessunit = bu.businessunitid
            WHERE e.recordstatus=1
            ORDER BY e.doj DESC
            LIMIT %s
        """, (limit,))
    except: return []


# ─── EMPLOYEES ───────────────────────────────────────────────────────────────

def get_employees(page=1, per_page=50, search=None, dept=None, vertical=None,
                  grade=None, branch=None, active_only=True, emp_type=None):
    offset = (page - 1) * per_page
    where = ["e.recordstatus=1"]
    args = []
    if active_only:
        where.append("e.activeflag=1")  # UI passes active_only=False to see all
    if search:
        where.append("(c.firstname LIKE %s OR c.lastname LIKE %s OR e.employeenumber LIKE %s OR CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) LIKE %s)")
        s = f"%{search}%"
        args += [s, s, s, s]
    if dept:
        where.append("e.departmentid=%s"); args.append(dept)
    if vertical:
        where.append("e.businessunit=%s"); args.append(vertical)
    if grade:
        where.append("e.gradeid=%s"); args.append(grade)
    if branch:
        where.append("e.branchid=%s"); args.append(branch)
    if emp_type:
        where.append("e.employeetypeid=%s"); args.append(emp_type)

    where_str = " AND ".join(where)

    total = q(f"SELECT COUNT(*) as cnt FROM employees e JOIN contact c ON e.contactid=c.contactid WHERE {where_str}", args, one=True)['cnt']

    rows = q(f"""
        SELECT e.employeeid, e.employeenumber, e.doj, e.dot, e.activeflag,
               e.gender, e.gradeid, e.branchid, e.departmentid, e.businessunit,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               c.firstname, c.lastname,
               d.departmentname,
               dt.typename as designation,
               g.typename as grade,
               b.branchesname,
               bu.businessunitname as vertical,
               et.typename as emptype,
               ep.filename as photo
        FROM employees e
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        LEFT JOIN designationtypes dt ON e.designationid = dt.typeid
        LEFT JOIN gradetypes g ON e.gradeid = g.typeid
        LEFT JOIN branches b ON e.branchid = b.branchid
        LEFT JOIN businessunit bu ON e.businessunit = bu.businessunitid
        LEFT JOIN employeetypes et ON e.employeetypeid = et.typeid
        LEFT JOIN employeephoto ep ON e.employeeid = ep.employeeid AND ep.recordstatus=1
        WHERE {where_str}
        ORDER BY c.firstname, c.lastname
        LIMIT %s OFFSET %s
    """, args + [per_page, offset])

    return {'rows': rows, 'total': total, 'page': page, 'per_page': per_page,
            'pages': (total + per_page - 1) // per_page}


def get_employee_full_profile(employeeid):
    try:
        emp = q("""
            SELECT e.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   c.firstname, c.lastname,
                   d.departmentname,
                   dt.typename as designation,
                   g.typename as grade,
                   b.branchesname,
                   bu.businessunitname as vertical,
                   et.typename as emptype,
                   CONCAT(mgr_c.firstname,' ',IFNULL(mgr_c.lastname,'')) as mgr_name,
                   mgr_e.employeenumber as mgr_number,
                   u.username, u.mobileattendanceflag, u.mobileaccess
            FROM employees e
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN departments d ON e.departmentid = d.departmentid
            LEFT JOIN designationtypes dt ON e.designationid = dt.typeid
            LEFT JOIN gradetypes g ON e.gradeid = g.typeid
            LEFT JOIN branches b ON e.branchid = b.branchid
            LEFT JOIN businessunit bu ON e.businessunit = bu.businessunitid
            LEFT JOIN employeetypes et ON e.employeetypeid = et.typeid
            LEFT JOIN employees mgr_e ON e.managerid = mgr_e.employeeid
            LEFT JOIN contact mgr_c ON mgr_e.contactid = mgr_c.contactid
            LEFT JOIN users u ON e.userid = u.userid
            WHERE e.employeeid = %s
        """, (employeeid,), one=True)

        if not emp:
            return None

        # Each sub-query wrapped independently so one failure doesn't kill the profile
        try:
            emp['bank'] = q("SELECT * FROM employeebank WHERE employeeid=%s AND recordstatus=1", (employeeid,))
        except: emp['bank'] = []

        try:
            emp['dependents'] = q("""
                SELECT ed.*, dt.typename as deptype
                FROM employeedependents ed
                JOIN dependenttypes dt ON ed.dependenttypeid = dt.typeid
                WHERE ed.employeeid=%s AND ed.recordstatus=1
            """, (employeeid,))
        except: emp['dependents'] = []

        try:
            emp['education'] = q("""
                SELECT ee.*,
                       el.typename as edlevel,
                       hd.degreename,
                       hm.majorname
                FROM employeeeducation ee
                LEFT JOIN hreducationlevel el ON ee.educationlevelid = el.typeid
                LEFT JOIN hrdegree hd ON ee.degreeid = hd.typeid
                LEFT JOIN hrmajor hm ON ee.majorid = hm.typeid
                WHERE ee.employeeid=%s AND ee.recordstatus=1
                ORDER BY ee.yearofcompletion DESC
            """, (employeeid,))
        except: emp['education'] = []

        try:
            emp['experience'] = q("""
                SELECT * FROM employeeexperiences
                WHERE employeeid=%s AND recordstatus=1
                ORDER BY startdate DESC
            """, (employeeid,))
        except: emp['experience'] = []

        try:
            emp['training'] = q("""
                SELECT * FROM employeetraining
                WHERE employeeid=%s AND recordstatus=1
                ORDER BY startdate DESC
            """, (employeeid,))
        except: emp['training'] = []

        try:
            emp['loans'] = q("""
                SELECT * FROM employeeloan
                WHERE employeeid=%s AND recordstatus=1
            """, (employeeid,))
        except: emp['loans'] = []

        try:
            emp['particulars'] = q("""
                SELECT ep.typename, epv.particularsvalue
                FROM employeeparticularsvalues epv
                JOIN employeeparticulars ep ON epv.particularsid = ep.typeid
                WHERE epv.employeeid=%s AND epv.recordstatus=1
            """, (employeeid,))
        except: emp['particulars'] = []

        emp['photo'] = None
        emp['imagepath'] = None

        return emp
    except Exception as ex:
        import traceback
        print(f"Profile error for empid {employeeid}: {ex}")
        traceback.print_exc()
        return None


# ─── ATTENDANCE ───────────────────────────────────────────────────────────────

def get_attendance_for_month(employeeid, year, month):
    try:
        return q("""
            SELECT da.attendanceid, da.attendancedate, da.ismobile, da.isreqularize,
                   at.typename as atttype, at.typecolour,
                   lt.typename as leavetype,
                   mar.resaon as mobile_reason, mar.lat, mar.lng, mar.address
            FROM dailyattendance da
            JOIN attendancetypes at ON da.attendancetypeid = at.typeid
            LEFT JOIN leavetypes lt ON da.leavetypeid = lt.typeid
            LEFT JOIN mobileattendancereason mar ON da.employeeid=mar.employeeid
                AND da.attendancedate=mar.attendancedate AND mar.recordstatus=1
            WHERE da.employeeid=%s
            AND YEAR(da.attendancedate)=%s AND MONTH(da.attendancedate)=%s
            AND da.recordstatus=1
            ORDER BY da.attendancedate
        """, (employeeid, year, month))
    except: return []


def get_attendance_summary_for_employee(employeeid, year=None):
    try:
        extra = "AND YEAR(da.attendancedate)=%s" if year else ""
        args = [employeeid, year] if year else [employeeid]
        return q(f"""
            SELECT at.typename, at.typecolour, COUNT(*) as cnt
            FROM dailyattendance da
            JOIN attendancetypes at ON da.attendancetypeid = at.typeid
            WHERE da.employeeid=%s AND da.recordstatus=1 {extra}
            GROUP BY at.typeid, at.typename, at.typecolour
        """, args)
    except: return []


def get_all_attendance_today():
    try:
        return q("""
            SELECT da.attendanceid, da.employeeid, da.attendancedate,
                   da.ismobile, da.isreqularize,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber,
                   d.departmentname,
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
            WHERE da.attendancedate = CURDATE() AND da.recordstatus=1
            ORDER BY empname
        """)
    except: return []


def get_mobile_attendance_history(employeeid=None, limit=100):
    try:
        where = "m.recordstatus=1"
        args = []
        if employeeid:
            where += " AND m.employeeid=%s"
            args.append(employeeid)
        return q(f"""
            SELECT m.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber, d.departmentname
            FROM mobileattendancereason m
            JOIN employees e ON m.employeeid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN departments d ON e.departmentid = d.departmentid
            WHERE {where}
            ORDER BY m.createddatetime DESC
            LIMIT %s
        """, args + [limit])
    except: return []


def upsert_attendance(employeeid, attendancedate, attendancetypeid,
                      leavetypeid, ismobile, created_by):
    existing = q("""
        SELECT attendanceid FROM dailyattendance
        WHERE employeeid=%s AND attendancedate=%s AND recordstatus=1
    """, (employeeid, attendancedate), one=True)

    if existing:
        execute("""
            UPDATE dailyattendance
            SET attendancetypeid=%s, leavetypeid=%s, ismobile=%s,
                modifiedby=%s, modifieddatetime=NOW()
            WHERE employeeid=%s AND attendancedate=%s AND recordstatus=1
        """, (attendancetypeid, leavetypeid, ismobile, created_by,
              employeeid, attendancedate))
        return existing['attendanceid']
    else:
        return execute("""
            INSERT INTO dailyattendance
            (employeeid, attendancedate, attendancetypeid, leavetypeid,
             ismobile, isreqularize, createdby, createddatetime,
             modifiedby, modifieddatetime, recordstatus)
            VALUES (%s,%s,%s,%s,%s,0,%s,NOW(),%s,NOW(),1)
        """, (employeeid, attendancedate, attendancetypeid, leavetypeid,
              ismobile, created_by, created_by))


def record_mobile_checkin(employeeid, attendancedate, reason, lat, lng,
                          address, created_by):
    return execute("""
        INSERT INTO mobileattendancereason
        (employeeid, attendancedate, resaon, lat, lng, address,
         createdby, createddatetime, modifiedby, modifieddatetime, recordstatus)
        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),%s,NOW(),1)
    """, (employeeid, attendancedate, reason, lat, lng, address,
          created_by, created_by))


def get_attendance_regulation_requests(employeeid=None, status=None, limit=100):
    try:
        where = ["arr.recordstatus=1"]
        args = []
        if employeeid:
            where.append("arr.requestpersionid=%s"); args.append(employeeid)
        if status == 'pending':
            where.append("arr.attendanceregulationflag=0")
        elif status == 'approved':
            where.append("arr.attendanceregulationflag=1")
        where_str = " AND ".join(where)
        return q(f"""
            SELECT arr.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber, at.typename as atttype
            FROM attendanceregulationrequest arr
            JOIN employees e ON arr.requestpersionid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            JOIN attendancetypes at ON arr.attendancetypeid = at.typeid
            WHERE {where_str}
            ORDER BY arr.requestdate DESC
            LIMIT %s
        """, args + [limit])
    except: return []


# ─── LEAVE ────────────────────────────────────────────────────────────────────

def get_leave_requests(employeeid=None, status=None, page=1, per_page=50):
    offset = (page - 1) * per_page
    where = ["lr.recordstatus=1"]
    args = []
    if employeeid:
        where.append("lr.requestpersionid=%s"); args.append(employeeid)
    if status == 'pending':
        where.append("lr.employeeleaveflag=0")
    elif status == 'approved':
        where.append("lr.employeeleaveflag=1")
    elif status == 'rejected':
        where.append("lr.employeeleaveflag=2")
    where_str = " AND ".join(where)

    total = q(f"SELECT COUNT(*) as cnt FROM leaverequest lr WHERE {where_str}",
              args, one=True)['cnt']
    rows = q(f"""
        SELECT lr.*, lt.typename as leavetype, lt.typecolor,
               CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
               e.employeenumber, d.departmentname
        FROM leaverequest lr
        JOIN leavetypes lt ON lr.leavetypeid = lt.typeid
        JOIN employees e ON lr.requestpersionid = e.employeeid
        JOIN contact c ON e.contactid = c.contactid
        LEFT JOIN departments d ON e.departmentid = d.departmentid
        WHERE {where_str}
        ORDER BY lr.requestdate DESC
        LIMIT %s OFFSET %s
    """, args + [per_page, offset])

    return {'rows': rows, 'total': total, 'page': page, 'per_page': per_page,
            'pages': (total + per_page - 1) // per_page}


def get_leave_balance(employeeid):
    try:
        leave_types = q("SELECT typeid, typename, typecolor, maxaccumulate FROM leavetypes WHERE recordstatus=1")
        balance = []
        for lt in leave_types:
            taken = q("""
                SELECT COALESCE(SUM(lr.noofdays),0) as taken
                FROM leaverequest lr
                WHERE lr.requestpersionid=%s AND lr.leavetypeid=%s
                AND lr.employeeleaveflag=1 AND lr.recordstatus=1
                AND YEAR(lr.startdate)=YEAR(CURDATE())
            """, (employeeid, lt['typeid']), one=True)['taken']
            pending = q("""
                SELECT COALESCE(SUM(lr.noofdays),0) as pending
                FROM leaverequest lr
                WHERE lr.requestpersionid=%s AND lr.leavetypeid=%s
                AND lr.employeeleaveflag=0 AND lr.recordstatus=1
                AND YEAR(lr.startdate)=YEAR(CURDATE())
            """, (employeeid, lt['typeid']), one=True)['pending']
            allotted = lt['maxaccumulate'] or 0
            balance.append({
                'leavetypeid': lt['typeid'],
                'typename': lt['typename'],
                'typecolor': lt['typecolor'],
                'allotted': allotted,
                'taken': float(taken),
                'pending': float(pending),
                'available': max(0, allotted - float(taken)),
            })
        return balance
    except: return []


def submit_leave_request(employeeid, leavetypeid, startdate, enddate,
                          noofdays, reason, contact_details, created_by, leave_number):
    return execute("""
        INSERT INTO leaverequest
        (leaverequestnumber, requestpersionid, leavetypeid, requestdate,
         noofdays, startdate, enddate, contactdetails, reasonforleave,
         employeeleaveflag, createdby, createddatetime,
         modifiedby, modifieddatetime, recordstatus)
        VALUES (%s,%s,%s,CURDATE(),%s,%s,%s,%s,%s,0,%s,NOW(),%s,NOW(),1)
    """, (leave_number, employeeid, leavetypeid, noofdays,
          startdate, enddate, contact_details, reason, created_by, created_by))


def approve_leave(leaverequestid, approver_employeeid, approve=True):
    flag = 1 if approve else 2
    execute("""
        UPDATE leaverequest SET employeeleaveflag=%s,
        modifiedby=%s, modifieddatetime=NOW()
        WHERE leaverequestid=%s
    """, (flag, str(approver_employeeid), leaverequestid))


# ─── CLAIMS / PAYROLL ─────────────────────────────────────────────────────────

def get_claim_vouchers(employeeid=None, page=1, per_page=50):
    try:
        offset = (page - 1) * per_page
        where = ["cv.recordstatus=1"]
        args = []
        if employeeid:
            where.append("cv.requestedbyid=%s"); args.append(employeeid)
        where_str = " AND ".join(where)
        total = q(f"SELECT COUNT(*) as cnt FROM claimvoucher cv WHERE {where_str}", args, one=True)["cnt"]
        rows = q(f"""
            SELECT cv.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber
            FROM claimvoucher cv
            JOIN employees e ON cv.requestedbyid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            WHERE {where_str}
            ORDER BY cv.createddatetime DESC
            LIMIT %s OFFSET %s
        """, args + [per_page, offset])
        return {"rows": rows, "total": total, "page": page, "per_page": per_page,
                "pages": max(1, (total+per_page-1)//per_page)}
    except Exception as ex:
        print(f"claimvoucher error: {ex}")
        return {"rows": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}


def get_claim_payments(employeeid=None, page=1, per_page=50):
    try:
        offset = (page - 1) * per_page
        where = ["cp.recordstatus=1"]
        args = []
        if employeeid:
            where.append("cp.paidtoid=%s"); args.append(employeeid)
        where_str = " AND ".join(where)
        total = q(f"SELECT COUNT(*) as cnt FROM claimpayment cp WHERE {where_str}",
                  args, one=True)['cnt']
        rows = q(f"""
            SELECT cp.*,
                   CONCAT(c1.firstname,' ',IFNULL(c1.lastname,'')) as paidto_name,
                   pd.paymentdesc as pay_type
            FROM claimpayment cp
            LEFT JOIN employees e1 ON cp.paidtoid = e1.employeeid
            LEFT JOIN contact c1 ON e1.contactid = c1.contactid
            LEFT JOIN paymentdesc pd ON cp.paymentdescid = pd.paymentdescid
            WHERE {where_str}
            ORDER BY cp.paymentdate DESC
            LIMIT %s OFFSET %s
        """, args + [per_page, offset])
        return {'rows': rows, 'total': total, 'page': page, 'per_page': per_page,
                'pages': (total + per_page - 1) // per_page}
    except: return {'rows': [], 'total': 0, 'page': 1, 'per_page': per_page, 'pages': 0}


def get_salary_structure(gradeid):
    try:
        return q("""
            SELECT gs.*, gt.typename as grade_name
            FROM gradesalarytype gs
            LEFT JOIN gradetypes gt ON gs.gradetypeid = gt.typeid
            WHERE gs.gradetypeid=%s AND gs.recordstatus=1
        """, (gradeid,))
    except: return []


def get_employee_loans(employeeid):
    try:
        return q("""
            SELECT * FROM employeeloan
            WHERE employeeid=%s AND recordstatus=1
        """, (employeeid,))
    except: return []


# ─── GRIEVANCE ───────────────────────────────────────────────────────────────

def get_grievances(employeeid=None, page=1, per_page=50):
    try:
        offset = (page - 1) * per_page
        where = ["g.recordstatus=1"]
        args = []
        if employeeid:
            where.append("g.employeeid=%s"); args.append(employeeid)
        where_str = " AND ".join(where)
        total = q(f"SELECT COUNT(*) as cnt FROM grievance g WHERE {where_str}", args, one=True)["cnt"]
        rows = q(f"""
            SELECT g.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as empname,
                   e.employeenumber,
                   gn.grievancenaturetype as nature,
                   gs.statustype as status_name
            FROM grievance g
            JOIN employees e ON g.employeeid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN grievancenature gn ON g.natureid = gn.grievancenatureid
            LEFT JOIN grievancestatus gs ON g.statusid = gs.grievancestatusid
            WHERE {where_str}
            ORDER BY g.gdate DESC
            LIMIT %s OFFSET %s
        """, args + [per_page, offset])
        return {"rows": rows, "total": total, "page": page, "per_page": per_page,
                "pages": max(1, (total+per_page-1)//per_page)}
    except Exception as ex:
        print(f"grievance error: {ex}")
        return {"rows": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}


def get_recruitment_requests(page=1, per_page=50):
    try:
        offset = (page - 1) * per_page
        total = q("SELECT COUNT(*) as cnt FROM recruitmentrequest WHERE recordstatus=1", one=True)["cnt"]
        rows = q("""
            SELECT rr.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as reqby_name
            FROM recruitmentrequest rr
            JOIN employees e ON rr.requesterid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            WHERE rr.recordstatus=1
            ORDER BY rr.createddatetime DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        return {"rows": rows, "total": total, "page": page, "per_page": per_page,
                "pages": max(1, (total+per_page-1)//per_page)}
    except Exception as ex:
        print(f"recruitment error: {ex}")
        return {"rows": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}


def get_candidates(recruitmentrequestid=None):
    try:
        where = "hc.recordstatus=1"
        args = []
        if recruitmentrequestid:
            where += " AND hc.recruitmentrequestid=%s"
            args.append(recruitmentrequestid)
        return q(f"SELECT * FROM hrcandidate hc WHERE {where} ORDER BY hc.createddatetime DESC", args)
    except: return []


# ─── KPI ─────────────────────────────────────────────────────────────────────

def get_kpi_targets(employeeid=None, fiscalyear=None):
    try:
        args = []
        extra = ""
        if employeeid:
            extra += " AND kt.kpiownerid=%s"; args.append(employeeid)
        if fiscalyear:
            extra += " AND kt.fiscalyear=%s"; args.append(fiscalyear)
        return q(f"""
            SELECT kt.*,
                   CONCAT(c.firstname,' ',IFNULL(c.lastname,'')) as owner_name,
                   e.employeenumber,
                   s.typename as vertical_name
            FROM kpitargets kt
            JOIN employees e ON kt.kpiownerid = e.employeeid
            JOIN contact c ON e.contactid = c.contactid
            LEFT JOIN sbutypes s ON kt.verticalid = s.typeid
            WHERE 1=1 {extra}
            ORDER BY kt.fiscalyear DESC
        """, args)
    except: return []


# ─── LOOKUPS ─────────────────────────────────────────────────────────────────

def get_departments():
    try: return q("SELECT departmentid, departmentname FROM departments WHERE recordstatus=1 ORDER BY departmentname")
    except: return []

def get_grades():
    try: return q("SELECT typeid, typename FROM gradetypes WHERE recordstatus=1 ORDER BY typename")
    except: return []

def get_designations():
    try: return q("SELECT typeid, typename FROM designationtypes WHERE recordstatus=1 ORDER BY typename")
    except: return []

def get_branches():
    try: return q("SELECT branchid, branchesname as branchname FROM branches WHERE recordstatus=1 ORDER BY branchname")
    except: return []

def get_verticals():
    try: return q("SELECT businessunitid, businessunitname FROM businessunit WHERE recordstatus=1 ORDER BY businessunitname")
    except: return []

def get_leave_types():
    try: return q("SELECT typeid, typename, typecolor FROM leavetypes WHERE recordstatus=1")
    except: return []

def get_attendance_types():
    try: return q("SELECT typeid, typename, typecolour FROM attendancetypes WHERE recordstatus=1")
    except: return []

def get_fiscal_years():
    try: return q("SELECT fiscalyearid, fiscalvalue, effectivitystartdate, effectivityenddate, iscurrent FROM fiscalyear WHERE recordstatus=1 ORDER BY effectivitystartdate DESC")
    except: return []

def get_current_fiscal_year():
    try: return q("SELECT * FROM fiscalyear WHERE iscurrent=1 AND recordstatus=1", one=True)
    except: return None

def get_holidays(year=None):
    try:
        if year:
            return q("SELECT * FROM holidaylist WHERE YEAR(holidaydate)=%s AND recordstatus=1 ORDER BY holidaydate", (year,))
        return q("SELECT * FROM holidaylist WHERE recordstatus=1 ORDER BY holidaydate DESC LIMIT 100")
    except: return []