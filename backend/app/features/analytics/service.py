"""Analytics service - event tracking, aggregations, segments, anomalies, user 360."""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlmodel import Session, select
from sqlalchemy import func, and_, desc

from features.analytics.models import (
    AnalyticsEvent, AnalyticsDailyAggregate, AnalyticsSegment, 
    AnalyticsFunnel, AnalyticsAnomaly
)


class AnalyticsService:
    """Main analytics service."""

    def __init__(self, session: Session):
        self.session = session
        # These classes live at the bottom of this module (moved from the
        # old core_analytics module). An earlier version referenced them as
        # `core_analytics.X` with no such import, so every method raised
        # NameError the moment it ran.
        self.tracker = AnalyticsTracker()
        self.aggregator = AggregationWorker(session)
        self.detector = AnomalyDetector(session)
        self.segment_engine = SegmentEngine(session)

    def track_event(
        self,
        event_name: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        platform: str = "web",
        app_version: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsEvent:
        """Track a single analytics event."""
        return self.tracker.track(
            self.session, event_name, user_id, session_id, platform, app_version, properties
        )

    def track_batch(self, events: List[TrackEvent]) -> List[AnalyticsEvent]:
        """Track multiple events efficiently."""
        return self.tracker.track_batch(self.session, events)

    def get_events(
        self,
        event_name: Optional[str] = None,
        user_id: Optional[int] = None,
        platform: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AnalyticsEvent]:
        return self.tracker.get_events(self.session, event_name, user_id, platform, since, until, limit)

    # Aggregations
    def run_daily_aggregation(self, target_date: Optional[datetime] = None) -> dict:
        """Run daily aggregation for a specific date."""
        return self.aggregator.run_daily_aggregation(target_date)

    def get_overview(self, days: int = 7) -> dict:
        """Get analytics overview for the last N days."""
        since = datetime.utcnow() - timedelta(days=days)
        now = datetime.utcnow()

        dau = self.session.exec(
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.created_at >= since, AnalyticsEvent.created_at <= now)
            .where(AnalyticsEvent.user_id.is_not(None))
        ).first() or 0

        wau = self.session.exec(
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.created_at >= now - timedelta(days=7))
            .where(AnalyticsEvent.user_id.is_not(None))
        ).first() or 0

        mau = self.session.exec(
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.created_at >= now - timedelta(days=30))
            .where(AnalyticsEvent.user_id.is_not(None))
        ).first() or 0

        new_signups = self.session.exec(
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.event_name == "signup")
            .where(AnalyticsEvent.created_at >= since)
        ).first() or 0

        # Retention D7
        retention_d7 = self._get_retention_rate(days=7)

        verified_rate = 0  # Would need user table join

        return {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "new_signups": new_signups,
            "retention_d7": retention_d7,
            "verified_rate": verified_rate,
        }

    def _get_retention_rate(self, days: int) -> float:
        """Calculate retention rate for N days."""
        # Simplified - would need proper cohort analysis
        return 0.0

    def get_feature_usage(self, days: int = 7) -> List[dict]:
        """Get feature usage stats."""
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(
                AnalyticsEvent.event_name,
                AnalyticsEvent.platform,
                func.count(AnalyticsEvent.id).label("count"),
                func.count(func.distinct(AnalyticsEvent.user_id)).label("unique_users"),
            )
            .where(AnalyticsEvent.created_at >= since)
            .group_by(AnalyticsEvent.event_name, AnalyticsEvent.platform)
        )
        rows = self.session.exec(stmt).all()
        return [
            {
                "feature": row.event_name,
                "platform": row.platform,
                "unique_users": row.unique_users,
                "opens": row.count,
            }
            for row in rows
        ]

    def get_retention(self, days: int = 7) -> dict:
        """Get retention metrics."""
        return {"d1": 0, "d7": 0, "d30": 0}

    def get_platform_versions(self, days: int = 7) -> List[dict]:
        """Get platform/version distribution."""
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(
                AnalyticsEvent.platform,
                AnalyticsEvent.app_version,
                func.count(AnalyticsEvent.id).label("count"),
                func.count(func.distinct(AnalyticsEvent.user_id)).label("unique_users"),
            )
            .where(AnalyticsEvent.created_at >= since)
            .group_by(AnalyticsEvent.platform, AnalyticsEvent.app_version)
        )
        rows = self.session.exec(stmt).all()
        return [
            {
                "platform": row.platform,
                "version": row.app_version or "unknown",
                "count": row.count,
                "unique_users": row.unique_users,
            }
            for row in rows
        ]

    # Segments
    def list_segments(self, is_active: Optional[bool] = None) -> List[AnalyticsSegment]:
        stmt = select(AnalyticsSegment)
        if is_active is not None:
            stmt = stmt.where(AnalyticsSegment.is_active == is_active)
        return self.session.exec(stmt.order_by(desc(AnalyticsSegment.created_at))).all()

    def create_segment(self, body, created_by: int) -> AnalyticsSegment:
        segment = AnalyticsSegment(
            name=body.name,
            description=body.description,
            criteria_json=body.criteria_json,
            created_by=created_by,
        )
        self.session.add(segment)
        self.session.commit()
        self.session.refresh(segment)
        return segment

    def get_segment(self, segment_id: int) -> Optional[AnalyticsSegment]:
        return self.session.get(AnalyticsSegment, segment_id)

    def update_segment(self, segment_id: int, body) -> Optional[AnalyticsSegment]:
        segment = self.session.get(AnalyticsSegment, segment_id)
        if not segment:
            return None
        update_data = body.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(segment, field, value)
        segment.updated_at = datetime.utcnow()
        self.session.add(segment)
        self.session.commit()
        self.session.refresh(segment)
        return segment

    def delete_segment(self, segment_id: int) -> bool:
        segment = self.session.get(AnalyticsSegment, segment_id)
        if not segment:
            return False
        self.session.delete(segment)
        self.session.commit()
        return True

    def get_segment_users(self, segment_id: int) -> List[int]:
        return self.segment_engine.get_segment_users(segment_id)

    # Funnels
    def create_funnel(self, body, created_by: int) -> AnalyticsFunnel:
        funnel = AnalyticsFunnel(
            name=body.name,
            description=body.description,
            steps_json=body.steps,
            window_hours=body.window_hours,
            created_by=created_by,
        )
        self.session.add(funnel)
        self.session.commit()
        self.session.refresh(funnel)
        return funnel

    def list_funnels(self, is_active: Optional[bool] = None) -> List[AnalyticsFunnel]:
        stmt = select(AnalyticsFunnel)
        if is_active is not None:
            stmt = stmt.where(AnalyticsFunnel.is_active == is_active)
        return self.session.exec(stmt.order_by(desc(AnalyticsFunnel.created_at))).all()

    def analyze_funnel(self, funnel_id: int, days: int = 7) -> dict:
        funnel = self.session.get(AnalyticsFunnel, funnel_id)
        if not funnel:
            return {"error": "Funnel not found"}

        results = []
        steps = funnel.steps_json
        for i, step in enumerate(steps):
            step_events = self.session.exec(
                select(func.count(func.distinct(AnalyticsEvent.user_id)))
                .where(AnalyticsEvent.event_name == step)
                .where(AnalyticsEvent.created_at >= datetime.utcnow() - timedelta(days=days))
            ).first() or 0

            if i == 0:
                results.append({"step": step, "users": step_events, "conversion": 100.0})
            else:
                prev_users = results[i-1]["users"]
                conv = (step_events / prev_users * 100) if prev_users > 0 else 0
                results.append({"step": step, "users": step_events, "conversion": round(conv, 2)})

        return {"funnel_id": funnel_id, "name": funnel.name, "steps": results}

    # Anomalies
    def list_anomalies(
        self, status: Optional[str] = None, severity: Optional[str] = None, days: int = 7
    ) -> List[AnalyticsAnomaly]:
        stmt = select(AnalyticsAnomaly).where(
            AnalyticsAnomaly.detected_at >= datetime.utcnow() - timedelta(days=days)
        )
        if status:
            stmt = stmt.where(AnalyticsAnomaly.status == status)
        if severity:
            stmt = stmt.where(AnalyticsAnomaly.severity == severity)
        return self.session.exec(stmt.order_by(desc(AnalyticsAnomaly.detected_at))).all()

    def update_anomaly(self, anomaly_id: int, status: str, user_id: int) -> Optional[AnalyticsAnomaly]:
        anomaly = self.session.get(AnalyticsAnomaly, anomaly_id)
        if not anomaly:
            return None
        anomaly.status = status
        if status == "acknowledged":
            anomaly.acknowledged_at = datetime.utcnow()
            anomaly.acknowledged_by = user_id
        elif status == "resolved":
            anomaly.resolved_at = datetime.utcnow()
            anomaly.acknowledged_by = user_id
        self.session.add(anomaly)
        self.session.commit()
        self.session.refresh(anomaly)
        return anomaly

    def detect_anomalies(self, target_date: Optional[datetime] = None) -> List[dict]:
        return self.detector.detect_anomalies(target_date)

    # User 360
    def get_user_360(self, user_id: int) -> dict:
        from models import User, UserProfile

        # Teams were removed from the product (the whole features/teams package
        # was deleted), so there is nothing to join here. The key stays as an
        # empty list because the User360 screen reads it.
        teams: list = []

        user = self.session.get(User, user_id)
        if not user:
            return {"error": "User not found"}

        profile = self.session.exec(
            select(UserProfile).where(UserProfile.user_id == user_id)
        ).first()

        # Events
        events = self.session.exec(
            select(AnalyticsEvent)
            .where(AnalyticsEvent.user_id == user_id)
            .order_by(desc(AnalyticsEvent.created_at))
            .limit(50)
        ).all()

        # (teams key set to [] above; the feature was removed)

        # Recent errors
        from features.errors.models import ErrorEvent
        errors = self.session.exec(
            select(ErrorEvent)
            .where(ErrorEvent.user_id == user_id)
            .order_by(desc(ErrorEvent.created_at))
            .limit(10)
        ).all()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name,
                "roll_number": user.roll_number,
                "role": user.role.value if user.role else None,
                "is_email_verified": user.is_email_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "profile": {
                # full_name lives on the account row and phone on the profile;
                # both are included here because the User360 screen renders them
                # from `profile`, and splitting them across two keys would push
                # a join onto the client.
                "full_name": user.full_name,
                "phone": profile.phone if profile else None,
                "branch": profile.branch if profile else None,
                "semester": profile.semester if profile else None,
                "programme": profile.programme if profile else None,
            } if profile or user.full_name else None,
            "recent_events": [
                {"event_name": e.event_name, "platform": e.platform, "created_at": e.created_at.isoformat()}
                for e in events
            ],
            "teams": teams,
            "recent_errors": [
                {"fingerprint": e.fingerprint_id, "platform": e.platform, "created_at": e.created_at.isoformat()}
                for e in errors
            ],
        }


# =============================================================================
# Core Analytics Classes (moved from core_analytics module)
# =============================================================================

@dataclass
class TrackEvent:
    event_name: str
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    platform: str = "web"
    app_version: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class AnalyticsTracker:
    """Track events and manage aggregations."""

    def __init__(self):
        self._buffer: List[AnalyticsEvent] = []
        self._buffer_size = 100
        self._flush_interval = 5  # seconds

    def track(
        self,
        session: Session,
        event_name: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        platform: str = "web",
        app_version: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> AnalyticsEvent:
        """Record an analytics event."""
        event = AnalyticsEvent(
            event_name=event_name,
            user_id=user_id,
            session_id=session_id,
            platform=platform,
            app_version=app_version,
            properties_json=properties,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    def track_batch(self, session: Session, events: List[TrackEvent]) -> List[AnalyticsEvent]:
        """Track multiple events efficiently."""
        events_to_add = [
            AnalyticsEvent(
                event_name=e.event_name,
                user_id=e.user_id,
                session_id=e.session_id,
                platform=e.platform,
                app_version=e.app_version,
                properties_json=e.properties,
            )
            for e in events
        ]
        session.add_all(events_to_add)
        session.commit()
        for e in events_to_add:
            session.refresh(e)
        return events_to_add

    def get_events(
        self,
        session: Session,
        event_name: Optional[str] = None,
        user_id: Optional[int] = None,
        platform: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AnalyticsEvent]:
        """Query events with filters."""
        stmt = select(AnalyticsEvent)
        if event_name:
            stmt = stmt.where(AnalyticsEvent.event_name == event_name)
        if user_id:
            stmt = stmt.where(AnalyticsEvent.user_id == user_id)
        if platform:
            stmt = stmt.where(AnalyticsEvent.platform == platform)
        if since:
            stmt = stmt.where(AnalyticsEvent.created_at >= since)
        if until:
            stmt = stmt.where(AnalyticsEvent.created_at <= until)
        stmt = stmt.order_by(AnalyticsEvent.created_at.desc()).limit(limit)
        return session.exec(stmt).all()


class AggregationWorker:
    """Daily aggregation worker for pre-computed metrics."""

    def __init__(self, session: Session):
        self.session = session

    def run_daily_aggregation(self, target_date: Optional[datetime] = None) -> dict:
        """Run daily aggregation for a specific date (default: yesterday)."""
        if target_date is None:
            target_date = datetime.utcnow().date() - timedelta(days=1)
        else:
            target_date = target_date.date()

        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        results = {
            "date": target_date.isoformat(),
            "aggregations": [],
        }

        # DAU/WAU/MAU
        dau = self._aggregate_dau(start, end)
        results["aggregations"].append(dau)

        # New signups
        signups = self._aggregate_signups(start, end)
        results["aggregations"].append(signups)

        # Feature usage
        feature_usage = self._aggregate_feature_usage(start, end)
        results["aggregations"].extend(feature_usage)

        # Retention cohorts (D1, D7, D30)
        retention = self._aggregate_retention(start, end)
        results["aggregations"].extend(retention)

        # Platform/version split
        platform_split = self._aggregate_platform_version(start, end)
        results["aggregations"].extend(platform_split)

        self.session.commit()
        return results

    def _aggregate_dau(self, start: datetime, end: datetime) -> dict:
        """Aggregate Daily Active Users."""
        count = self.session.exec(
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.created_at >= start, AnalyticsEvent.created_at < end)
            .where(AnalyticsEvent.user_id.is_not(None))
        ).first() or 0

        agg = AnalyticsDailyAggregate(
            date=start,
            metric_name="dau",
            dimension=None,
            dimension_value=None,
            count=count,
            unique_users=count,
        )
        self.session.add(agg)
        return {"metric": "dau", "count": count}

    def _aggregate_signups(self, start: datetime, end: datetime) -> dict:
        """Aggregate new user signups."""
        from models import User
        count = self.session.exec(
            select(func.count(User.id))
            .where(User.created_at >= start, User.created_at < end)
        ).first() or 0

        agg = AnalyticsDailyAggregate(
            date=start,
            metric_name="signups",
            dimension=None,
            dimension_value=None,
            count=count,
            unique_users=count,
        )
        self.session.add(agg)
        return {"metric": "signups", "count": count}

    def _aggregate_feature_usage(self, start: datetime, end: datetime) -> List[dict]:
        """Aggregate feature usage by feature name and platform."""
        stmt = (
            select(
                AnalyticsEvent.event_name,
                AnalyticsEvent.platform,
                func.count(AnalyticsEvent.id).label("count"),
                func.count(func.distinct(AnalyticsEvent.user_id)).label("unique_users"),
            )
            .where(AnalyticsEvent.created_at >= start, AnalyticsEvent.created_at < end)
            .group_by(AnalyticsEvent.event_name, AnalyticsEvent.platform)
        )
        rows = self.session.exec(stmt).all()

        results = []
        for row in rows:
            agg = AnalyticsDailyAggregate(
                date=start,
                metric_name="feature_usage",
                dimension="feature_platform",
                dimension_value=f"{row.event_name}:{row.platform}",
                count=row.count,
                unique_users=row.unique_users,
            )
            self.session.add(agg)
            results.append({
                "metric": "feature_usage",
                "feature": row.event_name,
                "platform": row.platform,
                "count": row.count,
                "unique_users": row.unique_users,
            })
        return results

    def _aggregate_retention(self, start: datetime, end: datetime) -> List[dict]:
        """Calculate D1, D7, D30 retention cohorts."""
        results = []
        for days_ago in [1, 7, 30]:
            cohort_start = start - timedelta(days=days_ago)
            cohort_end = cohort_start + timedelta(days=1)

            # Users who first appeared in cohort window
            cohort_users = self.session.exec(
                select(func.distinct(AnalyticsEvent.user_id))
                .where(AnalyticsEvent.created_at >= cohort_start, AnalyticsEvent.created_at < cohort_end)
                .where(AnalyticsEvent.user_id.is_not(None))
            ).all()

            if not cohort_users:
                continue

            user_ids = list(cohort_users)
            # How many returned in the target window?
            returned = self.session.exec(
                select(func.count(func.distinct(AnalyticsEvent.user_id)))
                .where(AnalyticsEvent.user_id.in_(user_ids))
                .where(AnalyticsEvent.created_at >= start, AnalyticsEvent.created_at < end)
            ).first() or 0

            total_cohort = len(user_ids)
            retention_rate = (returned / total_cohort * 100) if total_cohort > 0 else 0

            agg = AnalyticsDailyAggregate(
                date=start,
                metric_name=f"retention_d{days_ago}",
                dimension="cohort",
                dimension_value=f"d{days_ago}",
                count=returned,
                unique_users=returned,
                sum_value=retention_rate,
            )
            self.session.add(agg)
            results.append({
                "metric": f"retention_d{days_ago}",
                "cohort_size": total_cohort,
                "returned": returned,
                "rate_pct": round(retention_rate, 2),
            })
        return results

    def _aggregate_platform_version(self, start: datetime, end: datetime) -> List[dict]:
        """Aggregate by platform and app version."""
        stmt = (
            select(
                AnalyticsEvent.platform,
                AnalyticsEvent.app_version,
                func.count(AnalyticsEvent.id).label("count"),
                func.count(func.distinct(AnalyticsEvent.user_id)).label("unique_users"),
            )
            .where(AnalyticsEvent.created_at >= start, AnalyticsEvent.created_at < end)
            .group_by(AnalyticsEvent.platform, AnalyticsEvent.app_version)
        )
        rows = self.session.exec(stmt).all()

        results = []
        for row in rows:
            agg = AnalyticsDailyAggregate(
                date=start,
                metric_name="platform_version",
                dimension="platform_version",
                dimension_value=f"{row.platform}:{row.app_version or 'unknown'}",
                count=row.count,
                unique_users=row.unique_users,
            )
            self.session.add(agg)
            results.append({
                "metric": "platform_version",
                "platform": row.platform,
                "version": row.app_version or "unknown",
                "count": row.count,
                "unique_users": row.unique_users,
            })
        return results


class AnomalyDetector:
    """Detect anomalies using 7-day baseline ±3σ."""

    def __init__(self, session: Session):
        self.session = session

    def detect_anomalies(self, target_date: Optional[datetime] = None) -> List[dict]:
        """Detect anomalies for a given date (default: yesterday)."""
        if target_date is None:
            target_date = datetime.utcnow().date() - timedelta(days=1)
        else:
            target_date = target_date.date()

        target_start = datetime.combine(target_date, datetime.min.time())
        target_end = target_start + timedelta(days=1)

        # Baseline: last 7 days before target
        baseline_start = target_start - timedelta(days=7)
        baseline_end = target_start

        anomalies = []

        # Check key metrics
        metrics_to_check = [
            "dau",
            "signups",
            "feature_usage",
            "retention_d1",
            "retention_d7",
            "retention_d30",
        ]

        for metric in metrics_to_check:
            baseline_rows = self.session.exec(
                select(AnalyticsDailyAggregate)
                .where(AnalyticsDailyAggregate.metric_name == metric)
                .where(AnalyticsDailyAggregate.date >= baseline_start, AnalyticsDailyAggregate.date < baseline_end)
            ).all()

            if len(baseline_rows) < 3:  # Need minimum baseline
                continue

            baseline_values = [r.count + r.sum_value for r in baseline_rows]
            mean = sum(baseline_values) / len(baseline_values)
            std = (sum((v - mean) ** 2 for v in baseline_values) / len(baseline_values)) ** 0.5

            if std == 0:
                continue

            target_rows = self.session.exec(
                select(AnalyticsDailyAggregate)
                .where(AnalyticsDailyAggregate.metric_name == metric)
                .where(AnalyticsDailyAggregate.date >= target_start, AnalyticsDailyAggregate.date < target_end)
            ).all()

            for target_row in target_rows:
                actual = target_row.count + target_row.sum_value
                deviation = abs(actual - mean) / std if std > 0 else 0

                if deviation >= 3:  # 3-sigma
                    severity = "critical" if deviation >= 5 else "warning"
                    deviation_pct = ((actual - mean) / mean * 100) if mean != 0 else 0

                    anomaly = AnalyticsAnomaly(
                        metric_name=metric,
                        dimension=target_row.dimension,
                        dimension_value=target_row.dimension_value,
                        expected_value=round(mean, 2),
                        actual_value=round(actual, 2),
                        deviation_pct=round(deviation_pct, 2),
                        severity=severity,
                        description=f"{metric} deviated {deviation_pct:.1f}% from 7-day baseline (expected: {mean:.1f}, actual: {actual})",
                    )
                    self.session.add(anomaly)
                    self.session.commit()

                    anomalies.append({
                        "metric": metric,
                        "expected": round(mean, 2),
                        "actual": round(actual, 2),
                        "deviation_pct": round(deviation_pct, 2),
                        "severity": severity,
                    })

        return anomalies


class SegmentEngine:
    """User segment evaluation engine."""

    def __init__(self, session: Session):
        self.session = session

    def evaluate_segment(self, segment_criteria: dict, session: Session) -> List[int]:
        """Evaluate segment criteria and return matching user IDs."""
        from models import User
        from features.analytics.models import AnalyticsEvent

        stmt = select(User.id)

        conditions = []
        for rule in segment_criteria.get("and", []):
            field = rule["field"]
            operator = rule["operator"]
            values = rule.get("values", [rule.get("value")])

            if field == "platform":
                if operator == "in":
                    sub = select(AnalyticsEvent.user_id).where(
                        AnalyticsEvent.platform.in_(values)
                    ).distinct()
                    conditions.append(User.id.in_(sub))
            elif field == "last_active_days_ago":
                days = values[0]
                cutoff = datetime.utcnow() - timedelta(days=days)
                if operator == "gt":
                    sub = select(AnalyticsEvent.user_id).where(
                        AnalyticsEvent.created_at < cutoff
                    ).distinct()
                    conditions.append(User.id.in_(sub))
                elif operator == "lt":
                    sub = select(AnalyticsEvent.user_id).where(
                        AnalyticsEvent.created_at >= cutoff
                    ).distinct()
                    conditions.append(User.id.in_(sub))
            elif field == "feature_used" and operator == "in":
                sub = select(AnalyticsEvent.user_id).where(
                    AnalyticsEvent.event_name.in_(values)
                ).distinct()
                conditions.append(User.id.in_(sub))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # `select(User.id)` yields scalars, not row tuples - indexing would
        # raise "TypeError: 'int' object is not subscriptable" on every call.
        return list(session.exec(stmt).all())

    def get_segment_users(self, segment_id: int) -> List[int]:
        """Get user IDs for a saved segment."""
        segment = self.session.get(AnalyticsSegment, segment_id)
        if not segment:
            return []
        return self.evaluate_segment(segment.criteria_json, self.session)


# =============================================================================
# Module-level API: what `routes.py` calls.
# =============================================================================
#
# Every route calls `service.<name>(session, ...)` with the session first, but
# this module previously exposed only `AnalyticsService` methods, so every
# analytics endpoint raised AttributeError. These thin wrappers delegate to one
# service instance per call; the class keeps the real logic so both call styles
# stay consistent.

def _svc(session: Session) -> AnalyticsService:
    return AnalyticsService(session)


def track_event(
    session: Session,
    event_name: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    platform: str = "web",
    app_version: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> AnalyticsEvent:
    return _svc(session).track_event(
        event_name, user_id, session_id, platform, app_version, properties
    )


def track_batch(session: Session, events: List[TrackEvent]) -> List[AnalyticsEvent]:
    return _svc(session).track_batch(events)


def get_events(
    session: Session,
    event_name: Optional[str] = None,
    user_id: Optional[int] = None,
    platform: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 1000,
) -> List[AnalyticsEvent]:
    return _svc(session).get_events(
        event_name, user_id, platform, since, until, limit
    )


def run_daily_aggregation(
    session: Session, target_date: Optional[datetime] = None
) -> dict:
    return _svc(session).run_daily_aggregation(target_date)


def get_overview(session: Session, days: int = 7) -> dict:
    return _svc(session).get_overview(days)


def get_feature_usage(session: Session, days: int = 7) -> List[dict]:
    return _svc(session).get_feature_usage(days)


def get_retention(session: Session, days: int = 7) -> dict:
    return _svc(session).get_retention(days)


def get_platform_versions(session: Session, days: int = 7) -> List[dict]:
    return _svc(session).get_platform_versions(days)


def list_segments(
    session: Session, is_active: Optional[bool] = None
) -> list:
    return _svc(session).list_segments(is_active)


def create_segment(session: Session, body, created_by: int):
    return _svc(session).create_segment(body, created_by)


def get_segment(session: Session, segment_id: int):
    return _svc(session).get_segment(segment_id)


def update_segment(session: Session, segment_id: int, body):
    return _svc(session).update_segment(segment_id, body)


def delete_segment(session: Session, segment_id: int) -> bool:
    return _svc(session).delete_segment(segment_id)


def get_segment_users(session: Session, segment_id: int) -> List[int]:
    return _svc(session).get_segment_users(segment_id)


def create_funnel(session: Session, body, created_by: int):
    return _svc(session).create_funnel(body, created_by)


def list_funnels(session: Session, is_active: Optional[bool] = None) -> list:
    return _svc(session).list_funnels(is_active)


def analyze_funnel(session: Session, funnel_id: int, days: int = 7) -> dict:
    return _svc(session).analyze_funnel(funnel_id, days)


def list_anomalies(
    session: Session,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    days: int = 7,
) -> list:
    return _svc(session).list_anomalies(status, severity, days)


def update_anomaly(
    session: Session, anomaly_id: int, status: str, user_id: int
):
    return _svc(session).update_anomaly(anomaly_id, status, user_id)


def detect_anomalies(
    session: Session, target_date: Optional[datetime] = None
) -> List[dict]:
    return _svc(session).detect_anomalies(target_date)


def get_user_360(session: Session, user_id: int) -> dict:
    return _svc(session).get_user_360(user_id)