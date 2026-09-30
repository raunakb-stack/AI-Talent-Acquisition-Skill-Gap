import os
import secrets
from pathlib import Path
from datetime import date
from typing import Optional

from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ranking_skillgap import run

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
WEB_FILE = BASE_DIR / "website.html"

app = FastAPI(title="AI-Based Talent Acquisition & Skill Gap Analytics Platform", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "talent_acquisition"),
}
SESSIONS = {}


def db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as exc:
        raise HTTPException(503, f"MySQL connection failed: {exc}")


def rows(sql, params=()):
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close(); conn.close()


def execute(sql, params=(), many=False):
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        if many: cur.executemany(sql, params)
        else: cur.execute(sql, params)
        conn.commit(); return cur.lastrowid, cur.rowcount
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def auth(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer ") or authorization[7:] not in SESSIONS:
        raise HTTPException(401, "Login required")
    return SESSIONS[authorization[7:]]


def log_activity(user_id, action, entity, entity_id=None, details=None):
    try:
        execute("INSERT INTO Activity_Log(user_id,action,entity,entity_id,details) VALUES(%s,%s,%s,%s,%s)",
                (user_id, action, entity, entity_id, details))
    except Exception:
        pass


class Login(BaseModel):
    email: str
    password: str

class CandidateIn(BaseModel):
    name: str; email: str; phone: Optional[str] = None; experience_yrs: float = 0; highest_degree: str; resume_link: Optional[str] = None

class JobIn(BaseModel):
    job_title: str; dept_id: int; recruiter_id: int; experience_req: float = 0; salary_min: float = 0; salary_max: float = 0; status: str = "Open"

class ApplicationIn(BaseModel):
    candidate_id: int; job_id: int; status: str = "Applied"

class InterviewIn(BaseModel):
    application_id: int; interview_date: str; interviewer: str; feedback: Optional[str] = None; score_out_of_10: Optional[float] = None

class SkillIn(BaseModel):
    skill_name: str; category: str

class CandidateSkillIn(BaseModel):
    candidate_id: int; skill_id: int; proficiency: str

class JobSkillIn(BaseModel):
    job_id: int; skill_id: int; required_level: str; weight_pct: float = 100

class DeptIn(BaseModel):
    dept_name: str

class RecruiterIn(BaseModel):
    name: str; email: str; dept_id: int


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_FILE, media_type="text/html")

@app.get("/api/health")
def health():
    rows("SELECT 1 AS ok")
    return {"status":"ok", "database":"connected"}

@app.post("/api/login")
def login(body: Login):
    # Demo account is created by schema. Password is intentionally simple for a classroom mini-project.
    u = rows("SELECT user_id,email,name,role FROM Users WHERE email=%s AND password_hash=SHA2(%s,256) AND status='Active'", (body.email, body.password))
    if not u: raise HTTPException(401, "Invalid email or password")
    token = secrets.token_urlsafe(32); SESSIONS[token] = u[0]
    return {"token": token, "user": u[0]}

@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "): SESSIONS.pop(authorization[7:], None)
    return {"ok": True}

@app.get("/api/me")
def me(authorization: Optional[str] = Header(None)): return auth(authorization)

# ---------------- Master Data Management ----------------
@app.get("/api/departments")
def departments(authorization: Optional[str] = Header(None)):
    auth(authorization); return rows("SELECT * FROM Department ORDER BY dept_name")

@app.post("/api/departments")
def add_department(body: DeptIn, authorization: Optional[str] = Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Department(dept_name) VALUES(%s)",(body.dept_name,)); log_activity(u['user_id'],'CREATE','Department',i,body.dept_name); return {"id":i}

@app.get("/api/recruiters")
def recruiters(authorization: Optional[str] = Header(None)):
    auth(authorization); return rows("SELECT r.*,d.dept_name FROM Recruiter r JOIN Department d ON r.dept_id=d.dept_id ORDER BY r.name")

@app.post("/api/recruiters")
def add_recruiter(body: RecruiterIn, authorization: Optional[str] = Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Recruiter(name,email,dept_id) VALUES(%s,%s,%s)",(body.name,body.email,body.dept_id)); log_activity(u['user_id'],'CREATE','Recruiter',i,body.email); return {"id":i}

@app.get("/api/skills")
def skills(authorization: Optional[str] = Header(None)):
    auth(authorization); return rows("SELECT * FROM Skills ORDER BY skill_name")

@app.post("/api/skills")
def add_skill(body: SkillIn, authorization: Optional[str] = Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Skills(skill_name,category) VALUES(%s,%s)",(body.skill_name,body.category)); log_activity(u['user_id'],'CREATE','Skill',i,body.skill_name); return {"id":i}

# ---------------- Transaction / Activity Management ----------------
@app.get("/api/candidates")
def candidates(q: str = "", degree: str = "", min_exp: float = -1, authorization: Optional[str] = Header(None)):
    auth(authorization)
    sql="SELECT * FROM Candidate WHERE (name LIKE %s OR email LIKE %s)"; p=[f"%{q}%",f"%{q}%"]
    if degree: sql += " AND highest_degree=%s"; p.append(degree)
    if min_exp >= 0: sql += " AND experience_yrs >= %s"; p.append(min_exp)
    return rows(sql+" ORDER BY created_at DESC",p)

@app.post("/api/candidates")
def add_candidate(body: CandidateIn, authorization: Optional[str] = Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Candidate(name,email,phone,experience_yrs,highest_degree,resume_link) VALUES(%s,%s,%s,%s,%s,%s)",tuple(body.model_dump().values())); log_activity(u['user_id'],'CREATE','Candidate',i,body.email); return {"candidate_id":i}

@app.delete("/api/candidates/{cid}")
def delete_candidate(cid:int, authorization: Optional[str]=Header(None)):
    u=auth(authorization); execute("DELETE FROM Candidate WHERE candidate_id=%s",(cid,)); log_activity(u['user_id'],'DELETE','Candidate',cid); return {"ok":True}

@app.post("/api/candidate-skills")
def add_candidate_skill(body: CandidateSkillIn, authorization: Optional[str]=Header(None)):
    u=auth(authorization); execute("INSERT INTO Candidate_Skills(candidate_id,skill_id,proficiency) VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE proficiency=VALUES(proficiency)",(body.candidate_id,body.skill_id,body.proficiency)); log_activity(u['user_id'],'UPSERT','Candidate_Skills',body.candidate_id); return {"ok":True}

@app.get("/api/candidate-skills/{candidate_id}")
def candidate_skills(candidate_id:int, authorization: Optional[str]=Header(None)):
    auth(authorization)
    return rows("""SELECT cs.candidate_id,cs.skill_id,s.skill_name,s.category,cs.proficiency
                  FROM Candidate_Skills cs JOIN Skills s ON cs.skill_id=s.skill_id
                  WHERE cs.candidate_id=%s ORDER BY s.skill_name""", (candidate_id,))

@app.get("/api/job-skills/{job_id}")
def job_skills(job_id:int, authorization: Optional[str]=Header(None)):
    auth(authorization)
    return rows("""SELECT jrs.job_id,jrs.skill_id,s.skill_name,s.category,jrs.required_level,jrs.weight_pct
                  FROM Job_Required_Skills jrs JOIN Skills s ON jrs.skill_id=s.skill_id
                  WHERE jrs.job_id=%s ORDER BY s.skill_name""", (job_id,))

@app.post("/api/job-skills")
def add_job_skill(body: JobSkillIn, authorization: Optional[str]=Header(None)):
    u=auth(authorization)
    if body.weight_pct <= 0 or body.weight_pct > 100:
        raise HTTPException(400, "weight_pct must be between 0 and 100")
    execute("""INSERT INTO Job_Required_Skills(job_id,skill_id,required_level,weight_pct)
              VALUES(%s,%s,%s,%s)
              ON DUPLICATE KEY UPDATE required_level=VALUES(required_level), weight_pct=VALUES(weight_pct)""",
            (body.job_id,body.skill_id,body.required_level,body.weight_pct))
    log_activity(u['user_id'],'UPSERT','Job_Required_Skills',body.job_id)
    return {"ok":True}

@app.get("/api/jobs")
def jobs(q:str="", status:str="", authorization: Optional[str]=Header(None)):
    auth(authorization); sql="SELECT j.*,d.dept_name,r.name recruiter_name FROM Jobs j JOIN Department d ON j.dept_id=d.dept_id JOIN Recruiter r ON j.recruiter_id=r.recruiter_id WHERE j.job_title LIKE %s"; p=[f"%{q}%"]
    if status: sql+=" AND j.status=%s"; p.append(status)
    return rows(sql+" ORDER BY j.posted_on DESC,j.job_id DESC",p)

@app.post("/api/jobs")
def add_job(body: JobIn, authorization: Optional[str]=Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Jobs(job_title,dept_id,recruiter_id,experience_req,salary_min,salary_max,status) VALUES(%s,%s,%s,%s,%s,%s,%s)",tuple(body.model_dump().values())); log_activity(u['user_id'],'CREATE','Job',i,body.job_title); return {"job_id":i}

@app.delete("/api/jobs/{jid}")
def delete_job(jid:int, authorization: Optional[str]=Header(None)):
    u=auth(authorization); execute("DELETE FROM Jobs WHERE job_id=%s",(jid,)); log_activity(u['user_id'],'DELETE','Job',jid); return {"ok":True}

@app.get("/api/applications")
def applications(status:str="", authorization: Optional[str]=Header(None)):
    auth(authorization); sql="""SELECT a.*,c.name candidate_name,j.job_title FROM Applications a JOIN Candidate c ON a.candidate_id=c.candidate_id JOIN Jobs j ON a.job_id=j.job_id"""; p=[]
    if status: sql+=" WHERE a.status=%s"; p.append(status)
    return rows(sql+" ORDER BY a.applied_on DESC,a.application_id DESC",p)

@app.post("/api/applications")
def add_application(body: ApplicationIn, authorization: Optional[str]=Header(None)):
    u=auth(authorization)
    try: i,_=execute("INSERT INTO Applications(candidate_id,job_id,status) VALUES(%s,%s,%s)",(body.candidate_id,body.job_id,body.status))
    except Exception as exc: raise HTTPException(400,str(exc))
    log_activity(u['user_id'],'CREATE','Application',i)
    try:
        result=run(export_json=False)
    except Exception as exc:
        raise HTTPException(500, f"Application saved, but AI analysis failed: {exc}")
    return {"application_id":i,"ranking_updated":True,"dashboard":result}

@app.post("/api/interviews")
def add_interview(body: InterviewIn, authorization: Optional[str]=Header(None)):
    u=auth(authorization); i,_=execute("INSERT INTO Interview(application_id,interview_date,interviewer,feedback,score_out_of_10) VALUES(%s,%s,%s,%s,%s)",(body.application_id,body.interview_date,body.interviewer,body.feedback,body.score_out_of_10)); log_activity(u['user_id'],'CREATE','Interview',i); return {"interview_id":i}

# ---------------- AI/DS component ----------------
@app.post("/api/recalculate")
def recalculate(authorization: Optional[str]=Header(None)):
    u=auth(authorization); result=run(export_json=False); log_activity(u['user_id'],'RUN_AI_ANALYSIS','Candidate_Ranking'); return result

@app.get("/api/dashboard")
def dashboard_data(authorization: Optional[str]=Header(None)):
    auth(authorization); return run(export_json=False)

@app.get("/api/rankings")
def rankings(authorization: Optional[str]=Header(None)):
    auth(authorization); return rows("""SELECT r.ranking_id,c.name candidate_name,j.job_title,r.match_score,r.rank_position,r.generated_on FROM Candidate_Ranking r JOIN Applications a ON r.application_id=a.application_id JOIN Candidate c ON a.candidate_id=c.candidate_id JOIN Jobs j ON a.job_id=j.job_id ORDER BY j.job_title,r.rank_position""")

# ---------------- SQL Queries & Joins / Reports ----------------
@app.get("/api/sql-reports")
def sql_reports(authorization: Optional[str]=Header(None)):
    auth(authorization)
    return {
      "applicants_per_job": rows("SELECT j.job_title,COUNT(a.application_id) num_applicants FROM Jobs j LEFT JOIN Applications a ON j.job_id=a.job_id GROUP BY j.job_id,j.job_title ORDER BY num_applicants DESC"),
      "avg_interview_by_job": rows("SELECT j.job_title,ROUND(AVG(i.score_out_of_10),2) avg_score FROM Interview i JOIN Applications a ON i.application_id=a.application_id JOIN Jobs j ON a.job_id=j.job_id GROUP BY j.job_id,j.job_title"),
      "department_summary": rows("SELECT d.dept_name,ROUND(AVG(j.experience_req),1) avg_experience_required,COUNT(DISTINCT a.candidate_id) candidates_applied FROM Department d JOIN Jobs j ON d.dept_id=j.dept_id LEFT JOIN Applications a ON j.job_id=a.job_id GROUP BY d.dept_id,d.dept_name"),
      "education_summary": rows("SELECT highest_degree,COUNT(*) candidate_count FROM Candidate GROUP BY highest_degree ORDER BY candidate_count DESC"),
      "top_candidates": rows("SELECT * FROM Top_Candidates_View LIMIT 10")
    }

@app.get("/api/activity")
def activity(authorization: Optional[str]=Header(None)):
    auth(authorization); return rows("SELECT l.*,u.name user_name FROM Activity_Log l JOIN Users u ON l.user_id=u.user_id ORDER BY l.created_at DESC LIMIT 50")

@app.get("/api/db-concepts")
def db_concepts(authorization: Optional[str]=Header(None)):
    auth(authorization)
    return {
      "tables": rows("SELECT TABLE_NAME,ENGINE,TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",(DB_CONFIG['database'],)),
      "views": rows("SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s",(DB_CONFIG['database'],)),
      "routines": rows("SELECT ROUTINE_NAME,ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s",(DB_CONFIG['database'],)),
      "triggers": rows("SELECT TRIGGER_NAME,EVENT_MANIPULATION,TABLE_NAME,ACTION_TIMING FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s",(DB_CONFIG['database'],))
    }

@app.get('/er_diagram.png', include_in_schema=False)
def er_image(): return FileResponse(BASE_DIR/'er_diagram.png', media_type='image/png')

@app.get('/architecture_diagram.png', include_in_schema=False)
def arch_image(): return FileResponse(BASE_DIR/'architecture_diagram.png', media_type='image/png')
