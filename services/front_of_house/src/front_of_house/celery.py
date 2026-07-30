"""The Celery app — scheduled/delayed work only (DECISIONS.md §0003's
three-jobs table). Domain events fan out over Redis Streams, not Celery;
Celery's whole job here is countdown-scheduling the next cook-progression
step with `apply_async(countdown=...)`.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "front_of_house.settings")

app = Celery("front_of_house")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
