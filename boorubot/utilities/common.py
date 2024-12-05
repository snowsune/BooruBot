import logging

from datetime import datetime, timedelta, time


def seconds_until(_hour, _minute):
    """From stackoverflow and coppied by joe but will
    wait for a designated period of time and then resume."""

    given_time = time(hour=_hour, minute=_minute)
    now = datetime.now()
    future_exec = datetime.combine(now, given_time)
    if (
        future_exec - now
    ).days < 0:  # If we are past the execution, it will take place tomorrow
        future_exec = datetime.combine(
            now + timedelta(days=1), given_time
        )  # days always >= 0

    logging.debug(
        f"seconds_until: Seconds to wait.. {(future_exec - now).total_seconds()}"
    )
    return (future_exec - now).total_seconds()
