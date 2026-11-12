from datetime import date, datetime, time, timezone
from pytz import timezone as zona_horaria

BUENOS_AIRES = zona_horaria("America/Argentina/Buenos_Aires")


def hoy_local():
    return datetime.now(BUENOS_AIRES).date()


def fecha_bson(dia):
    return datetime.combine(dia, time.min, tzinfo=timezone.utc)


def limites_mes(dia):
    inicio = dia.replace(day=1)
    siguiente = date(dia.year + (dia.month == 12), dia.month % 12 + 1, 1)
    return fecha_bson(inicio), fecha_bson(siguiente)
