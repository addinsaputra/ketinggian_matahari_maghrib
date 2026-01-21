"""
Test Script for Maghrib Calculator - Monthly Schedule

Menghitung jadwal waktu Maghrib selama 1 bulan penuh
dengan integrasi data cuaca otomatis dari Open-Meteo ERA5 API.
Output disimpan dalam format Excel.
"""

from maghrib_calculator import (
    set_location,
    maghrib_time_local,
    sunrise_sunset_local,
    get_weather_data_auto
)
import calendar
import pandas as pd
from datetime import datetime

print("=" * 70)
print("MAGHRIB CALCULATOR - JADWAL 1 BULAN (EXCEL OUTPUT)")
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
test_date = (2024, 1, 15)

# ============================================
# HITUNG JADWAL MAGHRIB 1 BULAN PENUH
# ============================================

test_year = test_date[0]
test_month = test_date[1]

# Get number of days in the month
days_in_month = calendar.monthrange(test_year, test_month)[1]

# Set lokasi
loc = set_location(main_loc["lat"], main_loc["lon"], main_loc["elev"])

print(f"\nMemproses jadwal Maghrib untuk:")
print(f"Lokasi: {main_loc['name']}")
print(f"Koordinat: Lat {main_loc['lat']}, Lon {main_loc['lon']}, Elevasi: {main_loc['elev']} m")
print(f"Zona Waktu: {main_loc['tz']}")
print(f"Periode: {test_year}-{test_month:02d}-01 s/d {test_year}-{test_month:02d}-{days_in_month}")
print("-" * 70)

# List untuk menyimpan data
data_list = []

for day in range(1, days_in_month + 1):
    print(f"Memproses tanggal {test_year}-{test_month:02d}-{day:02d}...", end=" ")
    
    # Get weather data first
    try:
        temp_day, _ = get_weather_data_auto(loc, test_year, test_month, day, main_loc["tz"])
        temp_str = f"{temp_day:.1f}°C"
        temp_value = temp_day
    except Exception as e:
        temp_str = "N/A"
        temp_value = None
        print(f"Gagal mengambil data cuaca: {e}")

    try:
        sunrise, sunset = sunrise_sunset_local(loc, main_loc["tz"], test_year, test_month, day,
                                               auto_temperature=True, use_dynamic_radius=True)
        maghrib = maghrib_time_local(loc, main_loc["tz"], test_year, test_month, day,
                                     auto_temperature=True, use_dynamic_radius=True)
        
        # Format waktu
        sunrise_str = sunrise.strftime('%H:%M:%S') if sunrise else 'N/A'
        sunset_str = sunset.strftime('%H:%M:%S') if sunset else 'N/A'
        maghrib_str = maghrib.strftime('%H:%M:%S') if maghrib else 'N/A'
        
        print(f"✓ Maghrib: {maghrib_str}")
    except Exception as e:
        sunrise_str = 'N/A'
        sunset_str = 'N/A'
        maghrib_str = 'N/A'
        print(f"Gagal menghitung Maghrib: {e}")

    # Tambahkan ke list
    data_list.append({
        "Tanggal": f"{test_year}-{test_month:02d}-{day:02d}",
        "Sunrise": sunrise_str,
        "Sunset": sunset_str,
        "Maghrib": maghrib_str,
        "Suhu (°C)": temp_value,
        "Suhu_Teks": temp_str
    })

# ============================================
# SIMPAN KE EXCEL
# ============================================

print("\n" + "=" * 70)
print("Menyimpan ke Excel...")

# Buat DataFrame
df = pd.DataFrame(data_list)

# Hapus kolom Suhu_Teks (hanya untuk display)
df_final = df[["Tanggal", "Sunrise", "Sunset", "Maghrib", "Suhu (°C)"]]

# Generate nama file dengan timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"jadwal_maghrib_{test_year}_{test_month:02d}_{main_loc['name'].replace(' ', '_')}_{timestamp}.xlsx"

try:
    # Simpan ke Excel
    df_final.to_excel(filename, index=False, engine='openpyxl')
    print(f"✓ Berhasil disimpan: {filename}")
    print(f"✓ Total {len(data_list)} hari telah diproses")
except Exception as e:
    print(f"✗ Gagal menyimpan ke Excel: {e}")
    # Fallback: simpan ke CSV
    csv_filename = filename.replace('.xlsx', '.csv')
    try:
        df_final.to_csv(csv_filename, index=False)
        print(f"✓ Berhasil disimpan ke CSV (fallback): {csv_filename}")
    except Exception as e2:
        print(f"✗ Gagal menyimpan ke CSV: {e2}")

print("\n" + "=" * 70)
print("JADWAL MAGHRIB 1 BULAN SELESAI")
print("=" * 70)
