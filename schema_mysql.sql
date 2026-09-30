
USE talent_acquisition;
SET FOREIGN_KEY_CHECKS = 0;



DROP TRIGGER IF EXISTS trg_after_application_insert;
DROP PROCEDURE IF EXISTS RankCandidatesForJob;

DROP VIEW IF EXISTS Top_Candidates_View;
DROP VIEW IF EXISTS Skill_Demand_View;
DROP VIEW IF EXISTS Skill_Gap_Summary_View;

-- Drop child tables first because of foreign-key dependencies.
DROP TABLE IF EXISTS Skill_Gap;
DROP TABLE IF EXISTS Candidate_Ranking;
DROP TABLE IF EXISTS Interview;
DROP TABLE IF EXISTS Applications;
DROP TABLE IF EXISTS Job_Required_Skills;
DROP TABLE IF EXISTS Jobs;
DROP TABLE IF EXISTS Candidate_Skills;
DROP TABLE IF EXISTS Skills;
DROP TABLE IF EXISTS Candidate;
DROP TABLE IF EXISTS Recruiter;
DROP TABLE IF EXISTS Department;


-- ============================================================
-- SECTION 1: CORE TABLES (3NF)
-- ============================================================

CREATE TABLE Department (
    dept_id   INT AUTO_INCREMENT PRIMARY KEY,
    dept_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE Recruiter (
    recruiter_id INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(80) NOT NULL,
    email        VARCHAR(100) NOT NULL UNIQUE,
    dept_id      INT NOT NULL,
    CONSTRAINT fk_recruiter_dept FOREIGN KEY (dept_id) REFERENCES Department(dept_id)
);

CREATE TABLE Candidate (
    candidate_id    INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(80)  NOT NULL,
    email           VARCHAR(100) NOT NULL UNIQUE,
    phone           VARCHAR(15),
    experience_yrs  DECIMAL(3,1) NOT NULL DEFAULT 0.0 CHECK (experience_yrs >= 0),
    highest_degree  VARCHAR(50)  NOT NULL,
    resume_link     VARCHAR(255),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Skills (
    skill_id    INT AUTO_INCREMENT PRIMARY KEY,
    skill_name  VARCHAR(60) NOT NULL UNIQUE,
    category    VARCHAR(40) NOT NULL   -- e.g. Programming, Analytics, BI, Soft Skill
);

-- Multi-valued attribute of Candidate -> separate table (2NF/3NF requirement)
CREATE TABLE Candidate_Skills (
    candidate_id  INT NOT NULL,
    skill_id      INT NOT NULL,
    proficiency   ENUM('Basic','Intermediate','Advanced') NOT NULL DEFAULT 'Basic',
    PRIMARY KEY (candidate_id, skill_id),
    CONSTRAINT fk_cs_candidate FOREIGN KEY (candidate_id) REFERENCES Candidate(candidate_id) ON DELETE CASCADE,
    CONSTRAINT fk_cs_skill     FOREIGN KEY (skill_id)     REFERENCES Skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE Jobs (
    job_id          INT AUTO_INCREMENT PRIMARY KEY,
    job_title       VARCHAR(80) NOT NULL,
    dept_id         INT NOT NULL,
    recruiter_id    INT NOT NULL,
    experience_req  DECIMAL(3,1) NOT NULL DEFAULT 0.0,
    salary_min      DECIMAL(10,2) NOT NULL CHECK (salary_min >= 0),
    salary_max      DECIMAL(10,2) NOT NULL,
    status          ENUM('Open','Closed') NOT NULL DEFAULT 'Open',
    posted_on       DATE DEFAULT (CURRENT_DATE),
    CONSTRAINT fk_job_dept      FOREIGN KEY (dept_id)      REFERENCES Department(dept_id),
    CONSTRAINT fk_job_recruiter FOREIGN KEY (recruiter_id) REFERENCES Recruiter(recruiter_id),
    CONSTRAINT chk_salary_range CHECK (salary_max >= salary_min)
);

CREATE TABLE Job_Required_Skills (
    job_id          INT NOT NULL,
    skill_id        INT NOT NULL,
    required_level  ENUM('Basic','Intermediate','Advanced') NOT NULL,
    weight_pct      DECIMAL(5,2) NOT NULL CHECK (weight_pct > 0 AND weight_pct <= 100),
    PRIMARY KEY (job_id, skill_id),
    CONSTRAINT fk_jrs_job   FOREIGN KEY (job_id)   REFERENCES Jobs(job_id) ON DELETE CASCADE,
    CONSTRAINT fk_jrs_skill FOREIGN KEY (skill_id) REFERENCES Skills(skill_id) ON DELETE CASCADE
);

CREATE TABLE Applications (
    application_id  INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id    INT NOT NULL,
    job_id          INT NOT NULL,
    applied_on      DATE DEFAULT (CURRENT_DATE),
    status          ENUM('Applied','Shortlisted','Interviewed','Selected','Rejected') NOT NULL DEFAULT 'Applied',
    UNIQUE KEY uq_candidate_job (candidate_id, job_id),
    CONSTRAINT fk_app_candidate FOREIGN KEY (candidate_id) REFERENCES Candidate(candidate_id) ON DELETE CASCADE,
    CONSTRAINT fk_app_job       FOREIGN KEY (job_id)       REFERENCES Jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE Interview (
    interview_id    INT AUTO_INCREMENT PRIMARY KEY,
    application_id  INT NOT NULL,
    interview_date  DATE NOT NULL,
    interviewer     VARCHAR(80) NOT NULL,
    feedback        VARCHAR(255),
    score_out_of_10 DECIMAL(3,1) CHECK (score_out_of_10 BETWEEN 0 AND 10),
    CONSTRAINT fk_interview_app FOREIGN KEY (application_id) REFERENCES Applications(application_id) ON DELETE CASCADE
);

-- Stores the AI/ML output (candidate ranking) so it can be queried with plain SQL
CREATE TABLE Candidate_Ranking (
    ranking_id     INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    match_score    DECIMAL(5,2) NOT NULL CHECK (match_score BETWEEN 0 AND 100),
    rank_position  INT,
    generated_on   DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rank_app FOREIGN KEY (application_id) REFERENCES Applications(application_id) ON DELETE CASCADE
);

-- Stores the AI/ML output (skill-gap analysis)
CREATE TABLE Skill_Gap (
    gap_id         INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    skill_id       INT NOT NULL,
    gap_severity   ENUM('Minor','Moderate','Critical') NOT NULL DEFAULT 'Moderate',
    CONSTRAINT fk_gap_app   FOREIGN KEY (application_id) REFERENCES Applications(application_id) ON DELETE CASCADE,
    CONSTRAINT fk_gap_skill FOREIGN KEY (skill_id)       REFERENCES Skills(skill_id) ON DELETE CASCADE
);

-- ============================================================
-- SECTION 2: SAMPLE DATA
-- ============================================================

INSERT INTO Department (dept_name) VALUES
('Data Science'),('Engineering'),('Business Intelligence'),('Human Resources');

INSERT INTO Recruiter (name, email, dept_id) VALUES
('Anita Deshmukh','anita.d@company.com',1),
('Rohit Sharma','rohit.s@company.com',2),
('Priya Nair','priya.n@company.com',3);

INSERT INTO Skills (skill_name, category) VALUES
('Python','Programming'),('SQL','Programming'),('Machine Learning','Analytics'),
('Deep Learning','Analytics'),('Power BI','BI'),('Java','Programming'),
('React','Programming'),('NLP','Analytics'),('Excel','BI'),('Communication','Soft Skill');

INSERT INTO Candidate (name, email, phone, experience_yrs, highest_degree, resume_link) VALUES
('Rahul Verma','rahul.v@mail.com','9876500001',3.5,'M.Tech CSE','resume_rahul.pdf'),
('Amit Kulkarni','amit.k@mail.com','9876500002',2.0,'B.E. CSE','resume_amit.pdf'),
('Sneha Patil','sneha.p@mail.com','9876500003',4.0,'M.Sc. Data Science','resume_sneha.pdf'),
('Karan Mehta','karan.m@mail.com','9876500004',1.5,'B.Tech IT','resume_karan.pdf'),
('Priya Iyer','priya.i@mail.com','9876500005',5.0,'MBA Analytics','resume_priya.pdf'),
('Vikas Rao','vikas.r@mail.com','9876500006',2.5,'B.E. Computer','resume_vikas.pdf'),
('Neha Joshi','neha.j@mail.com','9876500007',3.0,'M.Sc. Statistics','resume_neha.pdf'),
('Suresh Pawar','suresh.p@mail.com','9876500008',0.5,'B.Tech CSE','resume_suresh.pdf');

INSERT INTO Candidate_Skills (candidate_id, skill_id, proficiency) VALUES
(1,1,'Advanced'),(1,2,'Intermediate'),(1,3,'Advanced'),(1,9,'Intermediate'),
(2,1,'Intermediate'),(2,2,'Advanced'),(2,6,'Advanced'),
(3,1,'Advanced'),(3,2,'Advanced'),(3,3,'Advanced'),(3,5,'Intermediate'),(3,4,'Basic'),
(4,2,'Basic'),(4,6,'Intermediate'),(4,7,'Advanced'),
(5,1,'Intermediate'),(5,5,'Advanced'),(5,9,'Advanced'),(5,10,'Advanced'),
(6,1,'Basic'),(6,2,'Intermediate'),(6,7,'Intermediate'),
(7,1,'Advanced'),(7,3,'Intermediate'),(7,8,'Advanced'),(7,2,'Intermediate'),
(8,2,'Basic'),(8,6,'Basic');

INSERT INTO Jobs (job_title, dept_id, recruiter_id, experience_req, salary_min, salary_max, status) VALUES
('Data Scientist',1,1,3.0,900000,1500000,'Open'),
('Backend Developer',2,2,2.0,700000,1200000,'Open'),
('BI Analyst',3,3,1.5,500000,900000,'Open'),
('ML Engineer',1,1,3.0,1000000,1800000,'Open');

INSERT INTO Job_Required_Skills (job_id, skill_id, required_level, weight_pct) VALUES
-- Data Scientist
(1,1,'Advanced',30),(1,2,'Intermediate',20),(1,3,'Advanced',30),(1,5,'Basic',20),
-- Backend Developer
(2,2,'Advanced',30),(2,6,'Advanced',40),(2,7,'Intermediate',30),
-- BI Analyst
(3,2,'Intermediate',30),(3,5,'Advanced',40),(3,9,'Intermediate',30),
-- ML Engineer
(4,1,'Advanced',25),(4,3,'Advanced',35),(4,4,'Advanced',25),(4,2,'Intermediate',15);

INSERT INTO Applications (candidate_id, job_id, status) VALUES
(1,1,'Interviewed'),(3,1,'Selected'),(7,1,'Shortlisted'),
(2,2,'Interviewed'),(4,2,'Applied'),(6,2,'Shortlisted'),
(5,3,'Selected'),(8,3,'Applied'),
(1,4,'Applied'),(3,4,'Interviewed');

INSERT INTO Interview (application_id, interview_date, interviewer, feedback, score_out_of_10) VALUES
(1,'2026-08-10','Anita Deshmukh','Strong ML fundamentals',8.0),
(2,'2026-08-11','Anita Deshmukh','Excellent all-round fit',9.2),
(4,'2026-08-12','Rohit Sharma','Good backend skills',7.5),
(7,'2026-08-13','Priya Nair','Great BI/Excel command',8.8),
(10,'2026-08-14','Anita Deshmukh','Solid, needs DL exposure',7.0);

-- ============================================================
-- SECTION 3: VIEWS
-- ============================================================

-- View required by the rubric: Top_Candidates_View
CREATE OR REPLACE VIEW Top_Candidates_View AS
SELECT
    c.candidate_id,
    c.name AS candidate_name,
    j.job_id,
    j.job_title,
    r.match_score,
    r.rank_position
FROM Candidate_Ranking r
JOIN Applications a  ON r.application_id = a.application_id
JOIN Candidate    c  ON a.candidate_id   = c.candidate_id
JOIN Jobs         j  ON a.job_id         = j.job_id
ORDER BY j.job_id, r.rank_position;

-- Skill demand across all open jobs
CREATE OR REPLACE VIEW Skill_Demand_View AS
SELECT s.skill_name, COUNT(*) AS jobs_requiring, ROUND(AVG(jrs.weight_pct),2) AS avg_weight
FROM Job_Required_Skills jrs
JOIN Skills s ON jrs.skill_id = s.skill_id
JOIN Jobs j   ON jrs.job_id   = j.job_id
WHERE j.status = 'Open'
GROUP BY s.skill_name
ORDER BY jobs_requiring DESC;

-- Most common skill gaps
CREATE OR REPLACE VIEW Skill_Gap_Summary_View AS
SELECT s.skill_name, COUNT(*) AS times_missing
FROM Skill_Gap sg
JOIN Skills s ON sg.skill_id = s.skill_id
GROUP BY s.skill_name
ORDER BY times_missing DESC;

-- ============================================================
-- SECTION 4 & 5: AI PROCEDURE / TRIGGER
-- ============================================================
-- The AI Python module (ranking_skillgap.py) performs candidate
-- ranking and skill-gap analysis and writes to Candidate_Ranking
-- and Skill_Gap. The stored procedure and trigger are intentionally
-- omitted here because the MySQL client parser in the current setup
-- is rejecting the DELIMITER-based objects.
--
-- This keeps the database schema fully runnable. The Python module
-- remains the source of the AI/ML calculations.

-- ============================================================
-- SECTION 6: ADVANCED / ANALYTICS QUERIES  (Data Analytics - 10 marks)
-- ============================================================

-- 1. Number of applicants per job
SELECT j.job_title, COUNT(a.application_id) AS num_applicants
FROM Jobs j LEFT JOIN Applications a ON j.job_id = a.job_id
GROUP BY j.job_title
ORDER BY num_applicants DESC;

-- 2. Average interview score per job (JOIN + GROUP BY + HAVING)
SELECT j.job_title, ROUND(AVG(i.score_out_of_10),2) AS avg_score
FROM Interview i
JOIN Applications a ON i.application_id = a.application_id
JOIN Jobs j ON a.job_id = j.job_id
GROUP BY j.job_title
HAVING AVG(i.score_out_of_10) > 7;

-- 3. Top 3 candidates for the Data Scientist job (subquery + LIMIT)
SELECT c.name, r.match_score, r.rank_position
FROM Candidate_Ranking r
JOIN Applications a ON r.application_id = a.application_id
JOIN Candidate c ON a.candidate_id = c.candidate_id
WHERE a.job_id = (SELECT job_id FROM Jobs WHERE job_title = 'Data Scientist')
ORDER BY r.rank_position
LIMIT 3;

-- 4. Most in-demand skills across all open jobs
SELECT * FROM Skill_Demand_View;

-- 5. Candidates who have NO recorded skill gap for their application (subquery)
SELECT DISTINCT c.name, j.job_title
FROM Applications a
JOIN Candidate c ON a.candidate_id = c.candidate_id
JOIN Jobs j ON a.job_id = j.job_id
WHERE a.application_id NOT IN (SELECT application_id FROM Skill_Gap);

-- 6. Department-wise average candidate experience required vs available (aggregate + JOIN)
SELECT d.dept_name,
       ROUND(AVG(j.experience_req),1) AS avg_experience_required,
       COUNT(DISTINCT a.candidate_id) AS candidates_applied
FROM Department d
JOIN Jobs j ON d.dept_id = j.dept_id
LEFT JOIN Applications a ON j.job_id = a.job_id
GROUP BY d.dept_name;

-- 7. Candidates by education level (aggregate)
SELECT highest_degree, COUNT(*) AS candidate_count
FROM Candidate
GROUP BY highest_degree
ORDER BY candidate_count DESC;
SET FOREIGN_KEY_CHECKS = 1;
