# AI-Based Talent Acquisition & Skill Gap Analytics Platform — DBMS Mini-Project

This version is intentionally designed as a **DBMS mini-project**. The database is the main system; the AI/DS part is a small transparent candidate matching/scoring component.

## Rubric coverage
1. Login/User Management — `Users`, FastAPI login, roles/status.
2. Master Data Management — Department, Recruiter, Skills, Candidate, Jobs.
3. Transaction/Activity Management — Applications, Interviews, Activity_Log, Application_Audit trigger.
4. Search & Filter — candidate and job search/filter APIs and website controls.
5. SQL Queries & Joins — JOIN, GROUP BY, HAVING, subqueries and aggregate reports in the SQL Reports page.
6. Reports & Dashboard — live KPIs, charts, rankings and reports.
7. AI/DS Analysis — skill matching + experience fit + education fit scoring and skill-gap classification.

## Database concepts
- ER diagram: `er_diagram.png`
- 3NF-oriented relational design
- PK/FK relationships
- UNIQUE, NOT NULL and CHECK constraints
- Views: `Top_Candidates_View`, `Skill_Demand_View`, `Skill_Gap_Summary_View`, `Application_Detail_View`, `Candidate_Profile_View`
- Stored procedure: `GetTopCandidates`
- Stored function: `ClassifyMatch`
- Trigger: `trg_after_application_insert`
- Audit table: `Application_Audit`

## Run
1. Start MySQL Server.
2. Run `schema_mysql.sql` once to create the main database/tables/sample data.
3. Run `dbms_upgrade.sql` to add login, activity, views, procedure, function and trigger.
4. Set `.env` or Windows environment variables:
   - `DB_HOST=127.0.0.1`
   - `DB_PORT=3306`
   - `DB_USER=root`
   - `DB_PASSWORD=your_password`
   - `DB_NAME=talent_acquisition`
5. Copy `.env.example` to `.env` and set `DB_PASSWORD` (keep `DB_NAME=talent_acquisition`).
6. Install dependencies: `pip install -r requirements.txt`
7. Start: `uvicorn app:app --reload --port 8000`
8. Open: `http://127.0.0.1:8000`

Demo login: `admin@talent.local` / `admin123`

## Automatic database update
All website create actions use FastAPI INSERT statements directly against the existing MySQL database. After a new application is created, the Python AI component recalculates `Candidate_Ranking` and `Skill_Gap`. MySQL Workbench will show the same updated records because it is connected to the same database.


## Website-to-MySQL connection
The website is served by FastAPI from `website.html`. The browser never connects directly to MySQL; it calls FastAPI endpoints, and FastAPI reads/writes the same `talent_acquisition` database visible in MySQL Workbench. The `.env` file is loaded automatically by both `app.py` and `ranking_skillgap.py`.

## Recommended first test
1. Log in with `admin@talent.local` / `admin123`.
2. Add a candidate.
3. Add/assign a skill to the candidate.
4. Create a job.
5. Add a required skill to that job.
6. Create an application.
7. The AI/DS module recalculates `Candidate_Ranking` and `Skill_Gap`.
8. In MySQL Workbench run `SELECT * FROM Candidate;`, `SELECT * FROM Applications;`, `SELECT * FROM Candidate_Ranking;` and `SELECT * FROM Skill_Gap;` to see the same updates.
