# -*- coding: utf-8 -*-
"""
Test Script for Sunrise Calculator - Monthly Schedule

Menghitung jadwal waktu Sunrise selama 1 bulan penuh
dengan integrasi data cuaca otomatis dari Open-Meteo ERA5 API.
Output disimpan dalam format Excel.

Output variabel:
- Tanggal
- Temperature (C)
- Pressure (mbar)
- Refraksi (deg)
- Ketinggian Matahari saat Sunrise (deg)
- Waktu Sunrise Lokal
- Sky Brightness (nanoLamberts)
- Extinction (K_V - mag/airmass)
"""

from sunmoon import (
    set_location,
    sunrise_sunset_local,
    get_weather_data_from_era5,
    refraction_horizon_degree,
    sun_position_time_local,
    moon_position_time_local,
    moon_phase_angle_time_local,
    convert_localtime_to_utc
)
from visual_limit_schaefer import visual_limit
import calendar
import pandas as pd
from datetime import datetime, timezone


def deg_to_dms(deg_value):
    """Convert decimal degrees to DMS string format."""
    if deg_value is None:
        return "N/A"
    
    deg_value = float(deg_value)
    sign = "-" if deg_value < 0 else ""
    deg_value = abs(deg_value)
    
    degrees = int(deg_value)
    minutes_float = (deg_value - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    return f"{sign}{degrees}° {minutes}' {seconds:.2f}\""


def calculate_azimuth_diff(az1, az2):
    """Calculate azimuth difference between two azimuths (0-180 degrees)."""
    diff = abs(az1 - az2)
    if diff > 180:
        diff = 360 - diff
    return diff


print("=" * 70)
print("SUNRISE CALCULATOR - JADWAL 1 BULAN (EXCEL OUTPUT)")
print("dengan Sky Brightness & Extinction dari Model Schaefer")
print("=" * 70)

# ============================================
# KONFIGURASI LOKASI DAN TANGGAL
# ============================================

# Lokasi utama (UIN Walisongo Semarang)
main_loc = {
    "name": "UIN Walisongo Semarang",
    "lat": -6.9751,
    "lon": 110.3997,
    "elev": 89,
    "tz": "Asia/Jakarta"
}

# Tanggal test (tahun, bulan, hari)
test_date = (2026, 1, 1)

# ============================================
# HITUNG JADWAL SUNRISE 1 BULAN PENUH
# ============================================

test_year = test_date[0]
test_month = test_date[1]

# Get number of days in the month
days_in_month = calendar.monthrange(test_year, test_month)[1]

# Set lokasi
loc = set_location(main_loc["lat"], main_loc["lon"], main_loc["elev"])

print(f"\nMemproses jadwal Sunrise untuk:")
print(f"Lokasi: {main_loc['name']}")
print(f"Koordinat: Lat {main_loc['lat']}, Lon {main_loc['lon']}, Elevasi: {main_loc['elev']} m")
print(f"Zona Waktu: {main_loc['tz']}")
print(f"Periode: {test_year}-{test_month:02d}-01 s/d {test_year}-{test_month:02d}-{days_in_month}")
print("-" * 70)

# List untuk menyimpan data
data_list = []

for day in range(1, days_in_month + 1):
    print(f"Memproses tanggal {test_year}-{test_month:02d}-{day:02d}...", end=" ")
    
    # Initialize default values
    temp_value = None
    pressure_value = None
    refraction_value = None
    sun_alt_value = None
    sun_az_value = None
    sunrise_str = "N/A"
    sky_brightness = None
    extinction_kv = None
    
    try:
        # Get weather data (temperature & pressure)
        target_utc = datetime(test_year, test_month, day, 0, 0, 0, tzinfo=timezone.utc)
        temp_value, pressure_value = get_weather_data_from_era5(
            loc, target_utc, main_loc["tz"], main_loc["name"]
        )
        
        # Calculate refraction at horizon
        refraction_value = refraction_horizon_degree(temp_value, pressure_value)
        
        # Calculate sunrise time using sunrise_sunset_local
        sunrise, _ = sunrise_sunset_local(
            loc, main_loc["tz"], test_year, test_month, day,
            temperature_C=temp_value, 
            pressure_mbar=pressure_value,
            auto_temperature=False
        )
        
        # Calculate sun altitude and azimuth at sunrise time
        if sunrise is not None:
            sun_alt, sun_az, _ = sun_position_time_local(
                loc, main_loc["tz"], local_datetime=sunrise,
                temperature_C=temp_value, pressure_mbar=pressure_value
            )
            sun_alt_value = sun_alt
            sun_az_value = sun_az
            sunrise_str = sunrise.strftime("%H:%M:%S")
            
            # Get moon position at sunrise time
            moon_alt, moon_az, _ = moon_position_time_local(
                loc, main_loc["tz"], local_datetime=sunrise,
                temperature_C=temp_value, pressure_mbar=pressure_value
            )
            
            # Get moon phase angle
            phase_angle = moon_phase_angle_time_local(
                main_loc["tz"], location=loc, local_datetime=sunrise
            )
            
            # Calculate azimuth differences (relative to zenith direction)
            # For sky brightness calculation, we use azimuth difference between objects
            azi_moon_diff = calculate_azimuth_diff(moon_az, 0)  # azimuth from reference
            azi_sun_diff = calculate_azimuth_diff(sun_az, 0)    # azimuth from reference
            
            # Calculate Sky Brightness and Extinction using Schaefer model
            # altstar = 90 untuk zenith (untuk mendapatkan kondisi langit umum)
            result = visual_limit(
                month=float(test_month),
                year=float(test_year),
                phase_angle=phase_angle,
                altmoon=moon_alt,
                azimoon=azi_moon_diff,
                altsun=sun_alt,
                azisun=azi_sun_diff,
                humidity=80.0,  # Default humidity (bisa diganti dengan data API)
                temperature=temp_value,
                latitude=main_loc["lat"],
                altitude=main_loc["elev"],
                snellen_ratio=1.0,
                altstar=45.0,  # Altitude objek pengamatan (45° sebagai referensi umum)
                goal_magnitude=99.0  # Hitung limiting magnitude
            )
            
            sky_brightness = result.get("sky_brightness", None)
            # Extinction coefficient untuk band V (index 2)
            extinction_kv = result.get("K", [None]*5)[2] if result.get("K") else None
        
        print(f"OK Sunrise: {sunrise_str} | T={temp_value:.1f}C | Sky={sky_brightness:.1f} nL" if sky_brightness else f"OK Sunrise: {sunrise_str}")
        
    except Exception as e:
        print(f"Error: {e}")

    # Tambahkan ke list
    row_data = {
        "Tanggal": f"{test_year}-{test_month:02d}-{day:02d}",
        "Temperature_C": None,
        "Pressure_mbar": None,
        "Refraksi_DMS": "N/A",
        "Tinggi_Matahari_DMS": "N/A",
        "Waktu_Sunrise": sunrise_str,
        "Sky_Brightness_nL": None,
        "Extinction_KV": None
    }
    
    if temp_value is not None:
        row_data["Temperature_C"] = round(float(temp_value), 2)
    if pressure_value is not None:
        row_data["Pressure_mbar"] = round(float(pressure_value), 2)
    if refraction_value is not None:
        row_data["Refraksi_DMS"] = deg_to_dms(refraction_value)
    if sun_alt_value is not None:
        row_data["Tinggi_Matahari_DMS"] = deg_to_dms(sun_alt_value)
    if sky_brightness is not None:
        row_data["Sky_Brightness_nL"] = round(float(sky_brightness), 2)
    if extinction_kv is not None:
        row_data["Extinction_KV"] = round(float(extinction_kv), 4)
    
    data_list.append(row_data)

# ============================================
# SIMPAN KE EXCEL
# ============================================

print("\n" + "=" * 70)
print("Menyimpan ke Excel...")

# Buat DataFrame
df = pd.DataFrame(data_list)

# Generate nama file dengan timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"jadwal_sunrise_{test_year}_{test_month:02d}_{main_loc['name'].replace(' ', '_')}_{timestamp}.xlsx"

try:
    # Simpan ke Excel
    df.to_excel(filename, index=False, engine="openpyxl")
    print(f"Berhasil disimpan: {filename}")
    print(f"Total {len(data_list)} hari telah diproses")
except Exception as e:
    print(f"Gagal menyimpan ke Excel: {e}")
    # Fallback: simpan ke CSV
    csv_filename = filename.replace(".xlsx", ".csv")
    try:
        df.to_csv(csv_filename, index=False)
        print(f"Berhasil disimpan ke CSV (fallback): {csv_filename}")
    except Exception as e2:
        print(f"Gagal menyimpan ke CSV: {e2}")

print("\n" + "=" * 70)
print("JADWAL SUNRISE 1 BULAN SELESAI")
print("=" * 70)

# Preview data
print("\nPreview data (5 hari pertama):")
print(df.head().to_string(index=False))
