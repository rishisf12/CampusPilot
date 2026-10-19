"""Seed script for OppFeed dev data.

Creates sample opportunities, source rules, search queries, and agent settings
so the faculty feed and admin dashboard have data to display on first run.

Safe to re-run: uses idempotent inserts (on conflict do nothing).
"""
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "app")

from sqlmodel import Session, select

from core.database import engine
from features.oppfeed.models import (
    Opportunity,
    OpportunityStatus,
    OpportunityType,
    WorkMode,
    DeadlineType,
    AgentSettings,
    SourceRule,
    SearchQuery,
)


def seed():
    with Session(engine) as db:
        # ---- Agent settings (idempotent) ----
        settings = db.exec(select(AgentSettings)).first()
        if not settings:
            settings = AgentSettings(
                run_window_start="02:00",
                run_window_end="04:00",
                auto_publish_enabled=False,
                auto_publish_threshold=0.85,
                llm_provider_chain="nvidia_nim,opencode_cli,openrouter,ollama,mock",
                llm_max_rpm=30,
                enable_agent=True,
                enable_scheduler=False,
                enable_vision=False,
                enable_banner_gen=False,
                enable_audio_summary=False,
            )
            db.add(settings)
            db.commit()
            print("Created AgentSettings")

        # ---- Source rules ----
        rules = [
            ("internshala.com", "allow", "Primary Indian internship aggregator"),
            ("freshersworld.com", "allow", "Entry-level jobs for freshers"),
            ("devfolio.co", "allow", "Hackathon platform"),
            ("unstop.com", "allow", "Student competitions and hackathons"),
            ("spam-site.example", "deny", "Known spam domain"),
        ]
        for domain, rule_type, desc in rules:
            existing = db.exec(
                select(SourceRule).where(SourceRule.domain == domain)
            ).first()
            if not existing:
                db.add(
                    SourceRule(domain=domain, rule_type=rule_type, description=desc)
                )
        db.commit()
        print("Created SourceRules")

        # ---- Search queries ----
        queries = [
            ("software engineering internship 2026", "tech", True, 10),
            ("data science internship", "tech", True, 9),
            ("product management internship", "mgmt", False, 8),
            ("UI UX design internship", "design", False, 7),
            ("hackathon October 2026", "events", True, 6),
        ]
        for query, category, enabled, priority in queries:
            existing = db.exec(
                select(SearchQuery).where(SearchQuery.query == query)
            ).first()
            if not existing:
                db.add(
                    SearchQuery(
                        query=query,
                        category=category,
                        enabled=enabled,
                        is_seed=True,
                        priority=priority,
                    )
                )
        db.commit()
        print("Created SearchQueries")

        # ---- Sample opportunities ----
        now = datetime.now(timezone.utc)
        opportunities = [
            {
                "slug": "google-swe-intern-2026",
                "status": OpportunityStatus.PUBLISHED,
                "title": "Software Engineer Intern - Summer 2026",
                "organization_name": "Google",
                "opportunity_type": OpportunityType.INTERNSHIP,
                "short_summary": "12-week software engineering internship for BTech/MTech students",
                "full_description": "Join Google's engineering team for a summer internship. Work on real products that impact millions of users.",
                "location": "Bangalore, India",
                "work_mode": WorkMode.HYBRID,
                "duration": "12 weeks",
                "start_date": "2026-06-01",
                "stipend_min": 80000,
                "stipend_max": 150000,
                "stipend_currency": "INR",
                "stipend_period": "month",
                "registration_start_date": now - timedelta(days=30),
                "registration_deadline": now + timedelta(days=45),
                "deadline_type": DeadlineType.FIXED,
                "education_levels": ["BTech", "MTech"],
                "allowed_branches": ["CSE", "ECE", "IT"],
                "graduation_years": [2026, 2027],
                "min_cgpa_or_percentage": 7.5,
                "skills_required": ["Python", "Java", "C++", "Data Structures"],
                "perks_benefits": ["Mentorship", "Certificate", "PPO opportunity"],
                "apply_url": "https://internshala.com/google-swe-2026",
                "source_domain": "internshala.com",
                "confidence_score": 0.95,
                "tags": ["sde", "internship", "google"],
                "published_at": now - timedelta(days=5),
            },
            {
                "slug": "microsoft-aml-intern-2026",
                "status": OpportunityStatus.APPROVED,
                "title": "Applied ML Intern",
                "organization_name": "Microsoft",
                "opportunity_type": OpportunityType.INTERNSHIP,
                "short_summary": "Machine learning internship focused on Azure AI services",
                "full_description": "Work with Microsoft's Azure AI team on applied machine learning problems.",
                "location": "Hyderabad, India",
                "work_mode": WorkMode.ONSITE,
                "duration": "6 months",
                "start_date": "2027-01-15",
                "stipend_min": 100000,
                "stipend_max": 180000,
                "stipend_currency": "INR",
                "stipend_period": "month",
                "registration_start_date": now - timedelta(days=15),
                "registration_deadline": now + timedelta(days=30),
                "deadline_type": DeadlineType.FIXED,
                "education_levels": ["MTech", "MS"],
                "allowed_branches": ["CSE"],
                "graduation_years": [2027],
                "min_cgpa_or_percentage": 8.0,
                "skills_required": ["Python", "PyTorch", "Machine Learning"],
                "perks_benefits": ["Mentorship", "Certificate", "Housing allowance"],
                "apply_url": "https://internshala.com/microsoft-aml-2026",
                "source_domain": "internshala.com",
                "confidence_score": 0.92,
                "tags": ["ml", "internship", "microsoft"],
            },
            {
                "slug": "devfolio-hackathon-oct-2026",
                "status": OpportunityStatus.PUBLISHED,
                "title": "DevFest Hackathon 2026",
                "organization_name": "Devfolio",
                "opportunity_type": OpportunityType.HACKATHON,
                "short_summary": "48-hour hackathon for student developers",
                "full_description": "Build something amazing in 48 hours. Prizes worth ₹5 lakhs.",
                "location": "Online",
                "work_mode": WorkMode.REMOTE,
                "duration": "48 hours",
                "start_date": now + timedelta(days=21),
                "stipend_min": None,
                "stipend_max": None,
                "stipend_currency": "INR",
                "stipend_period": None,
                "registration_start_date": now,
                "registration_deadline": now + timedelta(days=14),
                "deadline_type": DeadlineType.FIXED,
                "education_levels": ["BTech", "MTech", "BCA", "MCA"],
                "allowed_branches": ["CSE", "ECE", "IT"],
                "graduation_years": [2026, 2027, 2028],
                "min_cgpa_or_percentage": None,
                "skills_required": ["JavaScript", "React", "Node.js"],
                "perks_benefits": ["Prize money", "Swag", "Certificate"],
                "apply_url": "https://devfolio.co/hackathon-2026",
                "source_domain": "devfolio.co",
                "confidence_score": 0.98,
                "tags": ["hackathon", "devfolio", "online"],
                "published_at": now - timedelta(days=2),
            },
        ]
        for opp_data in opportunities:
            existing = db.exec(
                select(Opportunity).where(Opportunity.slug == opp_data["slug"])
            ).first()
            if not existing:
                db.add(Opportunity(**opp_data))
        db.commit()
        print("Created Opportunities")

        print("\nSeed complete!")


if __name__ == "__main__":
    seed()
