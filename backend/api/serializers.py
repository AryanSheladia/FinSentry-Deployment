from datetime import timezone


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc)
