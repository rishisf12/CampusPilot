from arq.connections import RedisSettings
from arq.worker import Worker
from app.core.config import settings as app_settings
from app.workers.tasks import send_email, wake_snooze, run_rule, send_reminder


def main():
    Worker(
        functions=[send_email, wake_snooze, run_rule, send_reminder],
        redis_settings=RedisSettings.from_dsn(app_settings.REDIS_URL),
    ).run()


if __name__ == "__main__":
    main()
