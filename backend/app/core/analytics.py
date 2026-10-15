"""Analytics event tracking and aggregation."""
from __future__ import annotations
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import hashlib
from sqlmodel import Session, select
from sqlalchemy import func, and_, or_

from features.analytics.models import AnalyticsEvent, AnalyticsDailyAggregate, AnalyticsSegment, AnalyticsAnomaly


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
        # Criteria format:
        # {
        #   "and": [
        #     {"field": "platform", "operator": "in", "values": ["web", "android"]},
        #     {"field": "last_active_days_ago", "operator": "gt", "value": 14},
        #     {"field": "feature_used", "operator": "in", "values": ["timetable", "exam"]}
        #   ]
        # }
        from models import User, AnalyticsEvent

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
            elif field == "feature_used":
                if operator == "in":
                    sub = select(AnalyticsEvent.user_id).where(
                        AnalyticsEvent.event_name.in_(values)
                    ).distinct()
                    conditions.append(User.id.in_(sub))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return [r[0] for r in session.exec(stmt).all()]

    def get_segment_users(self, segment_id: int) -> List[int]:
        """Get user IDs for a saved segment."""
        segment = self.session.get(AnalyticsSegment, segment_id)
        if not segment:
            return []
        return self.evaluate_segment(segment.criteria_json, self.session)