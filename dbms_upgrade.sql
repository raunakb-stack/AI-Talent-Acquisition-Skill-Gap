USE talent_acquisition;

-- ============================================================
-- DBMS UPGRADE SCRIPT
-- AI-Based Talent Acquisition & Skill Gap Analytics Platform
-- MySQL 8.0+
--
-- Run AFTER schema_mysql.sql
--
-- Includes:
-- 1. Login / User Management
-- 2. Transaction / Activity Management
-- 3. SQL Views
-- 4. Stored Function
-- 5. Stored Procedure
-- 6. Trigger
-- 7. Application Audit
-- 8. AI/DS Classification
-- ============================================================


-- ============================================================
-- 0. REMOVE ONLY OBJECTS CREATED BY THIS SCRIPT
-- ============================================================

DROP TRIGGER IF EXISTS trg_after_application_insert;

DROP PROCEDURE IF EXISTS GetTopCandidates;

DROP FUNCTION IF EXISTS ClassifyMatch;

DROP VIEW IF EXISTS Application_Detail_View;

DROP VIEW IF EXISTS Candidate_Profile_View;


-- ============================================================
-- 1. LOGIN / USER MANAGEMENT
-- ============================================================

CREATE TABLE IF NOT EXISTS Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash CHAR(64) NOT NULL,
    role ENUM('Admin','HR','Recruiter')
        NOT NULL DEFAULT 'HR',
    status ENUM('Active','Inactive')
        NOT NULL DEFAULT 'Active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- Demo Admin Account
-- Email: admin@talent.local
-- Password: admin123

INSERT INTO Users
    (name, email, password_hash, role, status)
VALUES
    (
        'System Admin',
        'admin@talent.local',
        SHA2('admin123',256),
        'Admin',
        'Active'
    )
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    role = VALUES(role),
    status = VALUES(status);


-- ============================================================
-- 2. TRANSACTION / ACTIVITY MANAGEMENT
-- ============================================================

CREATE TABLE IF NOT EXISTS Activity_Log (
    activity_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(40) NOT NULL,
    entity VARCHAR(50) NOT NULL,
    entity_id INT NULL,
    details VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_activity_user
        FOREIGN KEY (user_id)
        REFERENCES Users(user_id)
        ON DELETE CASCADE
);


-- ============================================================
-- 3. APPLICATION AUDIT TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS Application_Audit (
    audit_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    application_id INT NOT NULL,
    action_note VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_app
        FOREIGN KEY (application_id)
        REFERENCES Applications(application_id)
        ON DELETE CASCADE
);


-- ============================================================
-- 4. APPLICATION DETAIL VIEW
-- Demonstrates SQL JOINs
-- ============================================================

CREATE OR REPLACE VIEW Application_Detail_View AS
SELECT
    a.application_id,
    c.candidate_id,
    c.name AS candidate_name,
    c.email AS candidate_email,
    c.experience_yrs,
    c.highest_degree,
    j.job_id,
    j.job_title,
    d.dept_id,
    d.dept_name,
    a.status,
    a.applied_on
FROM Applications a
JOIN Candidate c
    ON a.candidate_id = c.candidate_id
JOIN Jobs j
    ON a.job_id = j.job_id
JOIN Department d
    ON j.dept_id = d.dept_id;


-- ============================================================
-- 5. CANDIDATE PROFILE VIEW
-- Demonstrates JOIN + GROUP_CONCAT + GROUP BY
-- ============================================================

CREATE OR REPLACE VIEW Candidate_Profile_View AS
SELECT
    c.candidate_id,
    c.name,
    c.email,
    c.experience_yrs,
    c.highest_degree,
    GROUP_CONCAT(
        CONCAT(
            s.skill_name,
            ' (',
            cs.proficiency,
            ')'
        )
        ORDER BY s.skill_name
        SEPARATOR ', '
    ) AS skills
FROM Candidate c
LEFT JOIN Candidate_Skills cs
    ON c.candidate_id = cs.candidate_id
LEFT JOIN Skills s
    ON cs.skill_id = s.skill_id
GROUP BY
    c.candidate_id,
    c.name,
    c.email,
    c.experience_yrs,
    c.highest_degree;


-- ============================================================
-- 6. AI / DS CLASSIFICATION FUNCTION
-- Simple score classification
-- ============================================================

CREATE FUNCTION ClassifyMatch(
    score DECIMAL(5,2)
)
RETURNS VARCHAR(20)
DETERMINISTIC
RETURN
    CASE
        WHEN score >= 80 THEN 'Strong Match'
        WHEN score >= 60 THEN 'Moderate Match'
        ELSE 'Low Match'
    END;


-- ============================================================
-- 7. STORED PROCEDURE
-- Returns top 10 candidates for a selected job
-- ============================================================

CREATE PROCEDURE GetTopCandidates(
    IN p_job_id INT
)
SELECT
    candidate_id,
    candidate_name,
    job_id,
    job_title,
    match_score,
    rank_position
FROM Top_Candidates_View
WHERE job_id = p_job_id
ORDER BY rank_position
LIMIT 10;


-- ============================================================
-- 8. TRIGGER
-- Automatically creates an audit record
-- whenever a new application is inserted
-- ============================================================

CREATE TRIGGER trg_after_application_insert
AFTER INSERT ON Applications
FOR EACH ROW
INSERT INTO Application_Audit
(
    application_id,
    action_note
)
VALUES
(
    NEW.application_id,
    'Application created'
);


-- ============================================================
-- 9. OPTIONAL ANALYTICS VIEW
-- Skill demand across open jobs
-- ============================================================

CREATE OR REPLACE VIEW Skill_Demand_View AS
SELECT
    s.skill_id,
    s.skill_name,
    COUNT(*) AS jobs_requiring,
    ROUND(AVG(jrs.weight_pct),2) AS avg_weight
FROM Job_Required_Skills jrs
JOIN Skills s
    ON jrs.skill_id = s.skill_id
JOIN Jobs j
    ON jrs.job_id = j.job_id
WHERE j.status = 'Open'
GROUP BY
    s.skill_id,
    s.skill_name;


-- ============================================================
-- 10. VERIFICATION
-- ============================================================

SELECT
    'Users table' AS verification,
    COUNT(*) AS records
FROM Users;


SELECT
    'Application Detail View' AS verification,
    COUNT(*) AS records
FROM Application_Detail_View;


SELECT
    'Candidate Profile View' AS verification,
    COUNT(*) AS records
FROM Candidate_Profile_View;


SELECT
    'Function Test' AS verification,
    ClassifyMatch(85) AS result;


SELECT
    'Procedure and DBMS objects created' AS verification;


SHOW TRIGGERS FROM talent_acquisition;


SHOW FULL TABLES
FROM talent_acquisition
WHERE Table_type = 'VIEW';


SHOW FUNCTION STATUS
WHERE Db = 'talent_acquisition';


SHOW PROCEDURE STATUS
WHERE Db = 'talent_acquisition';


-- ============================================================
-- END OF DBMS UPGRADE SCRIPT
-- ============================================================