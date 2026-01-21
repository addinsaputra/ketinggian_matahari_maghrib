"""
Maghrib Prayer Time Calculator

Modul ini menghitung waktu Maghrib berdasarkan perhitungan sunset (terbenamnya matahari)
dengan memperhitungkan koreksi elevasi lokasi, semi-diameter matahari (dinamis), dan refraksi atmosfer.

Perhitungan menggunakan:
- Skyfield untuk astronomi
- Ephemeris DE421 untuk posisi matahari akurat
- Koreksi refraksi atmosfer berdasarkan suhu dan tekanan
- Semi-diameter matahari dinamis berdasarkan jarak bumi-matahari
- Open-Meteo ERA5 API untuk data cuaca otomatis (temperature & pressure)
"""

import numpy as np
from skyfield import api
from skyfield import almanac
from datetime import datetime, timedelta, timezone
import re
import os
from skyfield.units import Angle

# Timezone handling
try:
	import pytz
	def _make_tz(tz_in):
		if tz_in is None:
			return pytz.timezone('UTC')
		if isinstance(tz_in, int):
			offset = int(tz_in)
			if offset >= 0:
				tz_name = f"Etc/GMT-{offset}"
			else:
				tz_name = f"Etc/GMT+{abs(offset)}"
			return pytz.timezone(tz_name)
		tzs = str(tz_in).strip()
		if re.fullmatch(r"[+-]?\\d+", tzs):
			offset = int(tzs)
			if offset >= 0:
				tz_name = f"Etc/GMT-{offset}"
			else:
				tz_name = f"Etc/GMT+{abs(offset)}"
			return pytz.timezone(tz_name)
		return pytz.timezone(tzs)

	def _localize(tz_obj, dt):
		return tz_obj.localize(dt)
except Exception:
	from zoneinfo import ZoneInfo

	def _make_tz(tz_in):
		if tz_in is None:
			return ZoneInfo('UTC')
		if isinstance(tz_in, int):
			offset = int(tz_in)
			if offset >= 0:
				tz_name = f"Etc/GMT-{offset}"
			else:
				tz_name = f"Etc/GMT+{abs(offset)}"
			return ZoneInfo(tz_name)
		tzs = str(tz_in).strip()
		if re.fullmatch(r"[+-]?\\d+", tzs):
			offset = int(tzs)
			if offset >= 0:
				tz_name = f"Etc/GMT-{offset}"
			else:
				tz_name = f"Etc/GMT+{abs(offset)}"
			return ZoneInfo(tz_name)
		return ZoneInfo(tzs)

	def _localize(tz_obj, dt):
		return dt.replace(tzinfo=tz_obj)

# Load ephemeris
ts = api.load.timescale()
_base_dir = os.path.dirname(__file__)
_ephem_path = os.path.join(_base_dir, 'de421.bsp')
if not os.path.exists(_ephem_path):
	_ephem_path = os.path.join(os.path.dirname(_base_dir), 'de421.bsp')
if not os.path.exists(_ephem_path):
	_ephem_path = os.path.join(os.getcwd(), 'de421.bsp')
ephem = api.load_file(_ephem_path)

__all__ = [
	"set_location",
	"get_weather_data_auto",
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
	"print_angle"
]


def set_location(latitude, longitude, elevation):
	"""Set lokasi pengamatan untuk perhitungan Maghrib.

	Parameters
	----------
	latitude : float
		Latitude dalam derajat (positif untuk Utara, negatif untuk Selatan)
	longitude : float
		Longitude dalam derajat (positif untuk Timur, negatif untuk Barat)
	elevation : float
		Elevasi dalam meter di atas permukaan laut

	Returns
	-------
	location : skyfield.toposlib.Topos
		Object lokasi yang digunakan untuk fungsi perhitungan Maghrib

	Example
	-------
	>>> loc = set_location(-6.2, 106.8, 10)  # Jakarta
	"""
	if latitude > 0:
		lat_str = '%lf N' % latitude
	else:
		lat_str = '%lf S' % (-1.0*latitude)

	if longitude > 0:
		long_str = '%lf E' % longitude
	else:
		long_str = '%lf W' % (-1.0*longitude)

	location = api.Topos(lat_str, long_str, elevation_m=elevation)
	return location


def get_weather_data_auto(location, year, month, day, time_zone_str="UTC"):
	"""Ambil data cuaca (temperature & pressure) secara otomatis dari Open-Meteo ERA5 API.

	Fungsi ini mengambil data temperature dan pressure pada waktu sunset untuk
	koreksi refraksi atmosfer yang lebih akurat.

	Parameters
	----------
	location : skyfield.toposlib.Topos
		Lokasi pengamatan dari set_location()
	year, month, day : int
		Tanggal untuk pengambilan data cuaca
	time_zone_str : str, optional
		Zona waktu untuk konversi waktu sunset ke UTC

	Returns
	-------
	tuple (temperature_C, pressure_mbar)
		temperature_C : Suhu dalam derajat Celsius
		pressure_mbar : Tekanan udara dalam milibar (default 1013.0 jika tidak tersedia)

	Example
	-------
	>>> loc = set_location(-6.2, 106.8, 10)
	>>> temp, pressure = get_weather_data_auto(loc, 2024, 1, 21, "Asia/Jakarta")
	"""
	try:
		# Import here to avoid dependency issues if API module not available
		from open_meteo_api_era5 import fetch_hourly_weather

		# Extract coordinates
		latitude = location.latitude.degrees
		longitude = location.longitude.degrees

		# Get sunset time approximation (using noon as reference)
		# This is used to determine which time of day to sample weather data
		date_str = f"{year:04d}-{month:02d}-{day:02d}"

		# Fetch hourly weather data for the date
		df_weather = fetch_hourly_weather(
			latitude=latitude,
			longitude=longitude,
			start_date=date_str,
			end_date=date_str,
			hourly_variables=["temperature_2m"],
			timezone="UTC"
		)

		# Get approximate sunset time (around 18:00 local time)
		# Convert to UTC for data lookup
		from datetime import timezone as tz
		local_tz = _make_tz(time_zone_str)
		sunset_approx = datetime(year, month, day, 18, 0, 0, tzinfo=local_tz)
		sunset_utc = sunset_approx.astimezone(tz.utc)

		# Find the data closest to sunset time
		df_weather['time_diff'] = abs(df_weather['date'] - sunset_utc)
		idx_closest = df_weather['time_diff'].idxmin()
		temp_c = float(df_weather.loc[idx_closest, 'temperature_2m'])

		# Pressure data not always available in ERA5 free tier, use standard value
		# TODO: Add pressure variable when available
		pressure_mbar = 1013.0

		return temp_c, pressure_mbar

	except Exception as e:
		# Fallback to default values if API fails
		print(f"Warning: Could not fetch weather data ({e}). Using default values.")
		return 28.0, 1013.0


def convert_utc_to_localtime(time_zone_str, utc_datetime=None, year=None, month=None, day=None, hour=None, minute=None, second=None):
	"""Konversi waktu UTC ke waktu lokal.

	Parameters
	----------
	time_zone_str : str
		Zona waktu (contoh: "Asia/Jakarta", "Asia/Makassar", "+7", "+8")
	utc_datetime : datetime, optional
		Datetime UTC (jika None, gunakan parameter year, month, day, etc.)
	year, month, day, hour, minute, second : int, optional
		Komponen waktu UTC

	Returns
	-------
	datetime
		Waktu dalam zona waktu lokal
	"""
	time_zone = _make_tz(time_zone_str)

	if utc_datetime is None:
		t = ts.utc(year, month=month, day=day, hour=hour, minute=minute, second=second)
		utc_datetime = t.utc_datetime()
		local_datetime = utc_datetime.astimezone(time_zone)
	else:
		local_datetime = utc_datetime.astimezone(time_zone)

	return local_datetime


def convert_localtime_to_utc(time_zone_str, local_datetime=None, year=None, month=None, day=None, hour=None, minute=None, second=None):
	"""Konversi waktu lokal ke UTC.

	Parameters
	----------
	time_zone_str : str
		Zona waktu (contoh: "Asia/Jakarta", "Asia/Makassar", "+7", "+8")
	local_datetime : datetime, optional
		Datetime lokal (jika None, gunakan parameter year, month, day, etc.)
	year, month, day, hour, minute, second : int, optional
		Komponen waktu lokal

	Returns
	-------
	datetime
		Waktu dalam UTC
	"""
	time_zone = _make_tz(time_zone_str)

	if local_datetime is None:
		d = datetime(year, month, day, hour, minute, int(second))
		tz = _localize(time_zone, d)
		t = ts.from_datetime(tz)
		utc_datetime = t.utc_datetime()
	else:
		if local_datetime.tzinfo is None:
			local_datetime = _localize(time_zone, local_datetime)
		t = ts.from_datetime(local_datetime)
		utc_datetime = t.utc_datetime()

	return utc_datetime


def refraction_horizon_degree(temperature_C, pressure_mbar):
	"""Hitung koreksi refraksi atmosfer pada horizon.

	Refraksi atmosfer menyebabkan matahari masih terlihat meskipun secara geometris
	sudah di bawah horizon. Koreksi ini bervariasi tergantung suhu dan tekanan.

	Parameters
	----------
	temperature_C : float
		Suhu dalam derajat Celsius
	pressure_mbar : float
		Tekanan udara dalam milibar

	Returns
	-------
	float
		Koreksi refraksi dalam derajat (biasanya ~0.5-0.6 derajat)
	"""
	from skyfield.earthlib import refraction

	r = refraction(0.0, temperature_C=temperature_C, pressure_mbar=pressure_mbar)
	return r


def sun_semidiameter_degrees(location, year=None, month=None, day=None, hour=None, minute=None, second=None, utc_datetime=None):
	"""Hitung semi-diameter (jari-jari angular) matahari pada waktu tertentu.

	Ukuran angular matahari bervariasi sepanjang tahun karena orbit bumi yang elips:
	- Perihelion (awal Januari): ~0.269 derajat (terbesar, bumi paling dekat dengan matahari)
	- Aphelion (awal Juli): ~0.266 derajat (terkecil, bumi paling jauh dari matahari)

	Variasi ini sekitar +/- 0.5% dan mempengaruhi waktu sunset/sunrise beberapa detik.

	Parameters
	----------
	location : skyfield.toposlib.Topos
		Lokasi pengamatan dari set_location()
	year, month, day, hour, minute, second : int, optional
		Waktu UTC
	utc_datetime : datetime, optional
		Alternatif cara spesifik waktu (datetime UTC timezone-aware)

	Returns
	-------
	float
		Semi-diameter matahari dalam derajat
	"""
	sun = ephem["Sun"]
	earth = ephem["Earth"]

	if utc_datetime is None:
		# Ensure all time components are specified (default to 0 if None)
		if hour is None:
			hour = 12  # Use noon as default for daily calculations
		if minute is None:
			minute = 0
		if second is None:
			second = 0
		t = ts.utc(year, month=month, day=day, hour=hour, minute=minute, second=second)
	else:
		from datetime import timezone as tz
		if utc_datetime.tzinfo is None:
			utc_datetime = utc_datetime.replace(tzinfo=tz.utc)
		t = ts.from_datetime(utc_datetime)

	# Calculate Earth-Sun distance using position vectors
	sun_pos = sun.at(t).position.km
	earth_pos = earth.at(t).position.km
	distance_km = np.linalg.norm(sun_pos - earth_pos)

	SUN_RADIUS_KM = 696342.0
	semi_diameter_rad = np.arcsin(SUN_RADIUS_KM / distance_km)
	semi_diameter_deg = np.degrees(semi_diameter_rad)

	return semi_diameter_deg


def sunrise_sunset_geometric_local(location, time_zone_str, year=None, month=None, day=None, use_dynamic_radius=False):
	"""Hitung sunrise/sunset TANPA koreksi refraksi atmosfer (hanya koreksi geometri/elevasi).

	Fungsi ini berguna untuk estimasi awal sebelum menerapkan koreksi refraksi.

	Parameters
	----------
	location : skyfield.toposlib.Topos
		Lokasi pengamatan dari set_location()
	time_zone_str : str
		Zona waktu (contoh: "Asia/Jakarta" atau "+7")
	year, month, day : int
		Tanggal untuk perhitungan
	use_dynamic_radius : bool, optional
		Jika True, hitung semi-diameter matahari secara dinamis. Default: False.

	Returns
	-------
	sunrise_local : datetime
		Waktu sunrise dalam waktu lokal
	sunset_local : datetime
		Waktu sunset dalam waktu lokal (TANPA koreksi refraksi)
	"""
	elev = location.elevation
	altitude_m = elev.m
	earth_radius_m = 6378136.6
	side_over_hypotenuse = earth_radius_m/(earth_radius_m + altitude_m)
	h = Angle(radians = -np.arccos(side_over_hypotenuse))

	horizon_degrees = h.degrees

	if use_dynamic_radius:
		radius_degrees = sun_semidiameter_degrees(location, year=year, month=month, day=day, hour=12, minute=0, second=0)
	else:
		radius_degrees = 0.2665

	t0 = ts.utc(year, month, day, 0)
	t1 = ts.utc(t0.utc_datetime() + timedelta(days=2))

	t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(ephem, ephem['Sun'], location,
													horizon_degrees=horizon_degrees, radius_degrees=radius_degrees))
	sunrise = None
	sunset = None
	for time, is_sunrise in zip(t, y):
		if is_sunrise:
			sunrise0 = time.utc_datetime()
			if (sunrise0.hour*60.0)+sunrise0.minute+(sunrise0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunrise0.day == day_plus1.day:
					sunrise = sunrise0
			else:
				if sunrise0.day == day:
					sunrise = sunrise0

		else:
			sunset0 = time.utc_datetime()
			if (sunset0.hour*60.0)+sunset0.minute+(sunset0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunset0.day == day_plus1.day:
					sunset = sunset0
			else:
				if sunset0.day == day:
					sunset = sunset0

	if sunrise is not None:
		sunrise_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunrise)
	else:
		sunrise_local = None
	sunset_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunset)

	return sunrise_local, sunset_local


def sunrise_sunset_apparent_local(location, time_zone_str, year=None, month=None, day=None,
								   temperature_C=10.0, pressure_mbar=1030.0, use_dynamic_radius=False, auto_temperature=False):
	"""Hitung sunrise/sunset DENGAN koreksi refraksi atmosfer.

	Fungsi ini memberikan waktu sunset yang paling akurat dengan memperhitungkan:
	1. Koreksi elevasi lokasi (dip of horizon)
	2. Semi-diameter matahari (statis atau dinamis)
	3. Refraksi atmosfer berdasarkan suhu dan tekanan

	ALUR PENGGUNAAN YANG DISARANKAN:
	1. Panggil sunrise_sunset_geometric_local() untuk estimasi awal
	2. Gunakan waktu tersebut untuk mengambil data suhu dari API/weather station
	3. Panggil fungsi ini dengan suhu aktual untuk hasil yang paling akurat

	Parameters
	----------
	location : skyfield.toposlib.Topos
		Lokasi pengamatan dari set_location()
	time_zone_str : str
		Zona waktu (contoh: "Asia/Jakarta" atau "+7")
	year, month, day : int
		Tanggal untuk perhitungan
	temperature_C : float, optional
		Suhu dalam derajat Celsius untuk koreksi refraksi. Default: 10.0
		Diabaikan jika auto_temperature=True.
	pressure_mbar : float, optional
		Tekanan udara dalam mbar untuk koreksi refraksi. Default: 1030.0
		Diabaikan jika auto_temperature=True.
	use_dynamic_radius : bool, optional
		Jika True, hitung semi-diameter matahari secara dinamis. Default: False.
	auto_temperature : bool, optional
		Jika True, ambil data temperature otomatis dari Open-Meteo API. Default: False.

	Returns
	-------
	sunrise_local : datetime
		Waktu sunrise dalam waktu lokal
	sunset_local : datetime
		Waktu sunset dalam waktu lokal DENGAN koreksi refraksi
	"""
	# Get weather data automatically if requested
	if auto_temperature:
		temperature_C, pressure_mbar = get_weather_data_auto(location, year, month, day, time_zone_str)

	elev = location.elevation
	altitude_m = elev.m
	earth_radius_m = 6378136.6
	side_over_hypotenuse = earth_radius_m/(earth_radius_m + altitude_m)
	h = Angle(radians = -np.arccos(side_over_hypotenuse))

	horizon_degrees = h.degrees - refraction_horizon_degree(temperature_C, pressure_mbar)

	if use_dynamic_radius:
		radius_degrees = sun_semidiameter_degrees(location, year=year, month=month, day=day, hour=12, minute=0, second=0)
	else:
		radius_degrees = 0.2665

	t0 = ts.utc(year, month, day, 0)
	t1 = ts.utc(t0.utc_datetime() + timedelta(days=2))

	t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(ephem, ephem['Sun'], location,
												horizon_degrees=horizon_degrees, radius_degrees=radius_degrees))

	sunrise = None
	sunset = None
	for time, is_sunrise in zip(t, y):
		if is_sunrise:
			sunrise0 = time.utc_datetime()
			if (sunrise0.hour*60.0)+sunrise0.minute+(sunrise0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunrise0.day == day_plus1.day:
					sunrise = sunrise0
			else:
				if sunrise0.day == day:
					sunrise = sunrise0
		else:
			sunset0 = time.utc_datetime()
			if (sunset0.hour*60.0)+sunset0.minute+(sunset0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunset0.day == day_plus1.day:
					sunset = sunset0
			else:
				if sunset0.day == day:
					sunset = sunset0

	if sunrise is not None:
		sunrise_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunrise)
	else:
		sunrise_local = None

	if sunset is not None:
		sunset_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunset)
	else:
		sunset_local = None

	return sunrise_local, sunset_local


def sunrise_sunset_utc(location, year=None, month=None, day=None, temperature_C=10.0, pressure_mbar=1030.0, use_dynamic_radius=False, auto_temperature=False, time_zone_str="UTC"):

	# Get weather data automatically if requested
	if auto_temperature:
		temperature_C, pressure_mbar = get_weather_data_auto(location, year, month, day, time_zone_str)

	elev = location.elevation
	altitude_m = elev.m
	earth_radius_m = 6378136.6
	side_over_hypotenuse = earth_radius_m/(earth_radius_m + altitude_m)
	h = Angle(radians = -np.arccos(side_over_hypotenuse))

	horizon_degrees = h.degrees - refraction_horizon_degree(temperature_C, pressure_mbar)

	if use_dynamic_radius:
		radius_degrees = sun_semidiameter_degrees(location, year=year, month=month, day=day, hour=12, minute=0, second=0)
	else:
		radius_degrees = 0.2665

	t0 = ts.utc(year, month, day, 0)
	t1 = ts.utc(t0.utc_datetime() + timedelta(days=2))

	t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(ephem, ephem['Sun'], location,
													horizon_degrees=horizon_degrees, radius_degrees=radius_degrees))

	sunrise = None
	sunset = None
	for time, is_sunrise in zip(t, y):
		if is_sunrise:
			sunrise0 = time.utc_datetime()
			if (sunrise0.hour*60.0)+sunrise0.minute+(sunrise0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunrise0.day == day_plus1.day:
					sunrise = sunrise0
			else:
				if sunrise0.day == day:
					sunrise = sunrise0

		else:
			sunset0 = time.utc_datetime()
			if (sunset0.hour*60.0)+sunset0.minute+(sunset0.second/60.0) + location.longitude.degrees*4 < 0.0:
				day_plus1 = datetime(year,month,day,0,0,0) + timedelta(days=1)
				if sunset0.day == day_plus1.day:
					sunset = sunset0
			else:
				if sunset0.day == day:
					sunset = sunset0

	return sunrise, sunset


def sunrise_sunset_local(location, time_zone_str, year=None, month=None, day=None, temperature_C=10.0, pressure_mbar=1030.0, use_dynamic_radius=False, auto_temperature=False):
	sunrise_utc, sunset_utc = sunrise_sunset_utc(location, year=year, month=month, day=day,
												temperature_C=temperature_C, pressure_mbar=pressure_mbar,
												use_dynamic_radius=use_dynamic_radius,
												auto_temperature=auto_temperature,
												time_zone_str=time_zone_str)
	sunrise_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunrise_utc)
	sunset_local = convert_utc_to_localtime(time_zone_str, utc_datetime=sunset_utc)

	return sunrise_local, sunset_local


def maghrib_time_local(location, time_zone_str, year=None, month=None, day=None,
					   temperature_C=10.0, pressure_mbar=1030.0, use_dynamic_radius=False,
					   add_minutes=0, auto_temperature=False):
	"""Hitung waktu sholat Maghrib (waktu sunset + tambahan jika diperlukan).

	Menurut mayoritas ulama, waktu Maghrib dimulai ketika matahari benar-benar
	telah terbenam (seluruh piringan matahari hilang di horizon).

	Parameters
	----------
	location : skyfield.toposlib.Topos
		Lokasi pengamatan dari set_location()
	time_zone_str : str
		Zona waktu (contoh: "Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "+7", "+8", "+9")
	year, month, day : int
		Tanggal untuk perhitungan
	temperature_C : float, optional
		Suhu dalam derajat Celsius untuk koreksi refraksi. Default: 10.0
		Diabaikan jika auto_temperature=True.
	pressure_mbar : float, optional
		Tekanan udara dalam mbar untuk koreksi refraksi. Default: 1030.0
		Diabaikan jika auto_temperature=True.
	use_dynamic_radius : bool, optional
		Jika True, hitung semi-diameter matahari secara dinamis. Default: False.
	add_minutes : float, optional
		Tambahan menit setelah sunset (untuk kehati-hatian/ijtihad). Default: 0.
	auto_temperature : bool, optional
		Jika True, ambil data temperature otomatis dari Open-Meteo API. Default: False.

	Returns
	-------
	datetime
		Waktu Maghrib dalam zona waktu lokal

	Example
	-------
	>>> loc = set_location(-6.2, 106.8, 10)  # Jakarta
	>>> maghrib = maghrib_time_local(loc, "Asia/Jakarta", 2026, 1, 21)
	>>> print(f"Maghrib: {maghrib.strftime('%H:%M:%S')}")

	# Dengan data cuaca otomatis
	>>> maghrib = maghrib_time_local(loc, "Asia/Jakarta", 2026, 1, 21, auto_temperature=True)
	"""
	# Get weather data automatically if requested
	if auto_temperature:
		temperature_C, pressure_mbar = get_weather_data_auto(location, year, month, day, time_zone_str)

	_, sunset_local = sunrise_sunset_apparent_local(
		location=location,
		time_zone_str=time_zone_str,
		year=year,
		month=month,
		day=day,
		temperature_C=temperature_C,
		pressure_mbar=pressure_mbar,
		use_dynamic_radius=use_dynamic_radius
	)

	if add_minutes > 0 and sunset_local is not None:
		maghrib = sunset_local + timedelta(minutes=add_minutes)
	else:
		maghrib = sunset_local

	return maghrib


def calc_timedelta_seconds(datetime1, datetime2):
	"""Hitung selisih dua datetime dalam detik.

	Parameters
	----------
	datetime1 : datetime
		Waktu awal
	datetime2 : datetime
		Waktu akhir

	Returns
	-------
	float
		Selisih waktu dalam detik
	"""
	timedelta = datetime2 - datetime1
	timedelta_s = (timedelta.days*86400.0) + timedelta.seconds
	return timedelta_s


def print_angle(angle_degree):
	"""Format sudut dalam derajat ke format derajat:menit:detik.

	Parameters
	----------
	angle_degree : float
		Sudut dalam derajat

	Returns
	-------
	str
		Sudut dalam format D°MM′SS.ss″
	"""
	return Angle(degrees=angle_degree).dstr(format=u'{0}{1}°{2:02}′{3:02}.{4:0{5}}″')
