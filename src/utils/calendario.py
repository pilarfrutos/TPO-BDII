from datetime import datetime, time, timezone


def fecha_bson(dia):
    return datetime.combine(dia, time.min, tzinfo=timezone.utc)
