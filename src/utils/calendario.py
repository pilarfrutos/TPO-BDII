from datetime import date, datetime, time, timedelta, timezone
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


def limites_ultimos_dias(dia, cantidad):
    """Devuelve [inicio, día siguiente) para ``cantidad`` fechas incluido ``dia``."""
    if cantidad < 1:
        raise ValueError("La cantidad de días debe ser positiva")
    inicio = dia - timedelta(days=cantidad - 1)
    return fecha_bson(inicio), fecha_bson(dia + timedelta(days=1))


def inicio_ultimo_anio(dia):
    """Devuelve el aniversario anterior, con el 28 de febrero como ajuste bisiesto."""
    if dia.month == 2 and dia.day == 29:
        return dia.replace(year=dia.year - 1, day=28)
    return dia.replace(year=dia.year - 1)
