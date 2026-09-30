"""
AI/ML COMPONENT — Candidate Ranking & Skill-Gap Analysis
=========================================================
MySQL-backed version for the AI-Based Talent Acquisition & Skill Gap
Analytics Platform.

Score model
-----------
    match_score = 0.65 * skill_match_pct
                + 0.20 * experience_fit_pct
                + 0.15 * education_fit_pct

The module reads the relational data from MySQL, calculates the AI/DS
candidate score and skill gaps, stores the results in Candidate_Ranking
and Skill_Gap, and can export dashboard/data.json for a standalone demo.

Configuration is read from environment variables:
    DB_HOST (default localhost)
    DB_PORT (default 3306)
    DB_USER (default root)
    DB_PASSWORD (required; your MySQL password)
    DB_NAME (default talent_acquisition)

Run:
    python ranking_skillgap.py
"""
import json
import os
from pathlib import Path
from collections import defaultdict

from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
OUT_PATH = HERE / "dashboard" / "data.json"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "talent_acquisition"),
}

PROF_ORDER = {"Basic": 1, "Intermediate": 2, "Advanced": 3}
EDU_SCORE = {
    "B.Tech IT": 70, "B.Tech CSE": 75, "B.E. Computer": 75, "B.E. CSE": 80,
    "M.Sc. Statistics": 82, "M.Sc. Data Science": 90, "M.Tech CSE": 92,
    "MBA Analytics": 88,
}


def connect():
    # If DB_PASSWORD is not set, ask for it securely at runtime.
    if not DB_CONFIG["password"]:
        from getpass import getpass
        DB_CONFIG["password"] = getpass("Enter MySQL root password: ")

    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(cursor, sql, params=None):
    cursor.execute(sql, params or ())
    return cursor.fetchall()


def skill_match_pct(cursor, candidate_id, job_id):
    cursor.execute(
        """
        SELECT jrs.skill_id, jrs.required_level, jrs.weight_pct,
               cs.proficiency
        FROM Job_Required_Skills jrs
        LEFT JOIN Candidate_Skills cs
               ON cs.candidate_id = %s AND cs.skill_id = jrs.skill_id
        WHERE jrs.job_id = %s
        """,
        (candidate_id, job_id),
    )
    rows = cursor.fetchall()
    total_weight = sum(float(r["weight_pct"]) for r in rows)
    earned = 0.0
    gaps = []

    for r in rows:
        proficiency = r["proficiency"]
        weight = float(r["weight_pct"])
        if proficiency is None:
            gaps.append((r["skill_id"], "missing"))
            continue

        have = PROF_ORDER[proficiency]
        need = PROF_ORDER[r["required_level"]]
        if have >= need:
            earned += weight
        else:
            earned += weight * 0.5
            gaps.append((r["skill_id"], "below_level"))

    pct = (earned / total_weight * 100) if total_weight else 0
    return round(pct, 2), gaps


def experience_fit_pct(candidate_yrs, required_yrs):
    candidate_yrs = float(candidate_yrs or 0)
    required_yrs = float(required_yrs or 0)
    if required_yrs <= 0:
        return 100.0
    return round(min(candidate_yrs / required_yrs, 1.0) * 100, 2)


def education_fit_pct(degree):
    return EDU_SCORE.get(degree, 65)


def make_json_serializable(value):
    """Convert MySQL-specific values (e.g. Decimal) into JSON-safe values."""
    from decimal import Decimal
    from datetime import date, datetime

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: make_json_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_serializable(v) for v in value]
    return value


def run(export_json=True):
    conn = None
    try:
        conn = connect()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT a.application_id, a.candidate_id, a.job_id,
                   c.name AS candidate_name, c.experience_yrs, c.highest_degree,
                   j.job_title, j.experience_req
            FROM Applications a
            JOIN Candidate c ON a.candidate_id = c.candidate_id
            JOIN Jobs j ON a.job_id = j.job_id
            ORDER BY a.application_id
            """
        )
        applications = cur.fetchall()

        # Recompute the AI/ML output cleanly on every run.
        cur.execute("DELETE FROM Candidate_Ranking")
        cur.execute("DELETE FROM Skill_Gap")

        cur.execute("SELECT skill_id, skill_name FROM Skills")
        skill_name = {r["skill_id"]: r["skill_name"] for r in cur.fetchall()}

        results = []
        for app in applications:
            sm_pct, gaps = skill_match_pct(cur, app["candidate_id"], app["job_id"])
            ex_pct = experience_fit_pct(app["experience_yrs"], app["experience_req"])
            ed_pct = education_fit_pct(app["highest_degree"])
            score = round(0.65 * sm_pct + 0.20 * ex_pct + 0.15 * ed_pct, 2)

            cur.execute(
                "INSERT INTO Candidate_Ranking (application_id, match_score) VALUES (%s, %s)",
                (app["application_id"], score),
            )

            for skill_id, kind in gaps:
                severity = "Critical" if kind == "missing" else "Minor"
                cur.execute(
                    """
                    INSERT INTO Skill_Gap
                        (application_id, skill_id, gap_severity)
                    VALUES (%s, %s, %s)
                    """,
                    (app["application_id"], skill_id, severity),
                )

            results.append({
                "application_id": app["application_id"],
                "candidate": app["candidate_name"],
                "job_id": app["job_id"],
                "job_title": app["job_title"],
                "skill_match_pct": sm_pct,
                "experience_fit_pct": ex_pct,
                "education_fit_pct": ed_pct,
                "match_score": score,
                "skill_gaps": [skill_name[s] for s, _ in gaps],
            })

        # Rank within each job using the same score shown by the AI module.
        by_job = defaultdict(list)
        for r in results:
            by_job[r["job_id"]].append(r)

        for rows in by_job.values():
            rows.sort(key=lambda x: (-x["match_score"], x["application_id"]))
            for i, r in enumerate(rows, start=1):
                r["rank"] = i
                cur.execute(
                    "UPDATE Candidate_Ranking SET rank_position=%s WHERE application_id=%s",
                    (i, r["application_id"]),
                )

        conn.commit()

        payload = build_dashboard_payload(cur, results)
        if export_json:
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(json.dumps(make_json_serializable(payload), indent=2), encoding="utf-8")
            print(f"Dashboard data exported to: {OUT_PATH}")

        print_report(by_job)
        return payload

    except Error as exc:
        if conn:
            conn.rollback()
        raise RuntimeError(
            "Could not connect to MySQL. Check that MySQL is running, the database "
            f"'{DB_CONFIG['database']}' exists, and DB_USER/DB_PASSWORD are correct. "
            f"MySQL error: {exc}"
        ) from exc
    finally:
        if conn and conn.is_connected():
            conn.close()


def build_dashboard_payload(cur, ranking_results):
    def q(sql):
        cur.execute(sql)
        return cur.fetchall()

    cur.execute("SELECT COUNT(*) AS n FROM Candidate")
    total_candidates = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM Jobs")
    total_jobs = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM Applications")
    total_applications = cur.fetchone()["n"]
    cur.execute("SELECT AVG(match_score) AS avg_score FROM Candidate_Ranking")
    avg_score = cur.fetchone()["avg_score"] or 0

    return {
        "kpis": {
            "total_candidates": int(total_candidates),
            "total_jobs": int(total_jobs),
            "total_applications": int(total_applications),
            "avg_match_score": round(float(avg_score), 2),
        },
        "skill_demand": q("SELECT * FROM Skill_Demand_View"),
        "skill_gap_summary": q("SELECT * FROM Skill_Gap_Summary_View"),
        "applicants_per_job": q(
            """
            SELECT j.job_title, COUNT(a.application_id) AS num_applicants
            FROM Jobs j
            LEFT JOIN Applications a ON j.job_id = a.job_id
            GROUP BY j.job_title
            ORDER BY num_applicants DESC
            """
        ),
        "top_candidates": sorted(
            ranking_results, key=lambda x: (-x["match_score"], x["application_id"])
        )[:5],
        "all_rankings": ranking_results,
    }


def print_report(by_job):
    print("=" * 70)
    print("CANDIDATE RANKING + SKILL-GAP REPORT")
    print("=" * 70)
    for job_id, rows in sorted(by_job.items()):
        print(f"\nJob: {rows[0]['job_title']}")
        print("-" * 50)
        for r in sorted(rows, key=lambda x: x["rank"]):
            gap_txt = ", ".join(r["skill_gaps"]) if r["skill_gaps"] else "None"
            print(
                f"  #{r['rank']}  {r['candidate']:<15} "
                f"score={r['match_score']:>6.2f}%  gaps: {gap_txt}"
            )


if __name__ == "__main__":
    run()
