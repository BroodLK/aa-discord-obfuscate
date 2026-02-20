"""Create or enable periodic tasks for discord_obfuscate."""

# Django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Discord Obfuscate App


class Command(BaseCommand):
    help = "Create or enable periodic Celery beat tasks for discord_obfuscate."

    def handle(self, *args, **options):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask
        except Exception as exc:
            raise CommandError(
                "django_celery_beat is required to create periodic tasks."
            ) from exc

        hourly = {
            "minute": "0",
            "hour": "*/1",
            "day_of_week": "*",
            "day_of_month": "*",
            "month_of_year": "*",
            "timezone": settings.TIME_ZONE,
        }
        every_three_days = {
            "minute": "0",
            "hour": "0",
            "day_of_week": "*",
            "day_of_month": "*/3",
            "month_of_year": "*",
            "timezone": settings.TIME_ZONE,
        }

        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "Obfuscate Discord: Sync all roles",
            "discord_obfuscate.tasks.periodic_sync_all_roles",
            hourly,
        )
        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "Obfuscate Discord: Rotate random keys",
            "discord_obfuscate.tasks.periodic_rotate_random_keys",
            every_three_days,
        )
        self._ensure_periodic_task(
            PeriodicTask,
            CrontabSchedule,
            "Obfuscate Discord: Sync role colors",
            "discord_obfuscate.tasks.periodic_sync_role_colors",
            hourly,
        )

    def _ensure_periodic_task(
        self,
        PeriodicTask,
        CrontabSchedule,
        name: str,
        task_path: str,
        schedule: dict,
    ):
        minute = schedule.get("minute", "0")
        hour = schedule.get("hour", "*/1")
        day_of_week = schedule.get("day_of_week", "*")
        day_of_month = schedule.get("day_of_month", "*")
        month_of_year = schedule.get("month_of_year", "*")
        timezone = schedule.get("timezone")

        task = PeriodicTask.objects.filter(name=name).first()
        if task:
            update_fields = []
            if task.task != task_path:
                task.task = task_path
                update_fields.append("task")
            if not task.enabled:
                task.enabled = True
                update_fields.append("enabled")
            if update_fields:
                task.save(update_fields=update_fields)
                self.stdout.write(f"Updated periodic task '{name}'.")
            else:
                self.stdout.write(f"Periodic task '{name}' already exists.")
            return

        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
            timezone=timezone,
        )

        task = PeriodicTask.objects.create(
            name=name,
            task=task_path,
            crontab=crontab,
            enabled=True,
        )

        self.stdout.write(
            f"Created periodic task '{task.name}' with schedule {minute} {hour} "
            f"{day_of_month} {month_of_year} {day_of_week} ({timezone})."
        )
