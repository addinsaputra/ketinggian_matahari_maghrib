"""
Maghrib Prayer Time Calculator - Wrapper Module

Modul ini adalah wrapper untuk kompatibilitas backward.
Semua fungsi inti sudah dipindahkan ke sunmoon.py.

Untuk penggunaan baru, disarankan import langsung dari sunmoon.py:
    from sunmoon import set_location, maghrib_time_local, get_weather_data_from_era5
"""

# Re-export semua fungsi dari sunmoon.py untuk backward compatibility
from sunmoon import (
    set_location,
    get_weather_data_from_era5,
    convert_utc_to_localtime,
    convert_localtime_to_utc,
    refraction_horizon_degree,
    sun_semidiameter_degrees,
    sunrise_sunset_geometric_local,
    sunrise_sunset_apparent_local,
    sunrise_sunset_utc,
    sunrise_sunset_local,
    maghrib_time_local,
    calc_timedelta_seconds,
    print_angle,
)

# Alias for backward compatibility
get_weather_data_auto = get_weather_data_from_era5

__all__ = [
    "set_location",
    "get_weather_data_auto",
    "get_weather_data_from_era5",
    "convert_utc_to_localtime",
    "convert_localtime_to_utc",
    "refraction_horizon_degree",
    "sun_semidiameter_degrees",
    "sunrise_sunset_geometric_local",
    "sunrise_sunset_apparent_local",
    "sunrise_sunset_utc",
    "sunrise_sunset_local",
    "maghrib_time_local",
    "calc_timedelta_seconds",
    "print_angle",
]
