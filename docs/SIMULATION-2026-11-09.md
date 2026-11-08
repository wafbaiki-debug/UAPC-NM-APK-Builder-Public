# UAPC NM Controller — simulasi pemeriksaan sumber (9 November 2026)

## Skop
Pemeriksaan statik fail `builder/generate.py` pada branch `feat/uapc-controller-apk-20261109` melalui sambungan GitHub. **Bukan** ujian Android runtime, bukan ujian Java compile, bukan pengesahan APK install. Cubaan clone melalui persekitaran tempatan gagal kerana DNS `github.com` tidak tersedia.

## Keputusan 11 pemeriksaan
1. Klasifikasi objective controller — PASS_STATIC.
2. Pengesanan pendua case-insensitive — PASS_STATIC.
3. Simpan rekod SharedPreferences — PASS_STATIC.
4. Pulihkan rekod JSON — PASS_STATIC.
5. Dialog pengesahan padam — PASS_STATIC.
6. Tanda siap melalui checkbox — PASS_STATIC.
7. Kiraan kemajuan objektif siap — PASS_STATIC.
8. Butang daftar objektif — PASS_STATIC.
9. Manifest tanpa permintaan permission tambahan — PASS_STATIC.
10. Aset logo nyamuk rasmi — MISSING.
11. Worker automatik sebenar — MISSING.

## Batasan
Semakan ini hanya mengesahkan kewujudan laluan kod; ia tidak membuktikan aliran butang berfungsi, ketahanan simpanan selepas restart, pencegahan pendua runtime, ataupun Android APK boleh dipasang. Kena bina APK, semak laporan artifact, pasang pada peranti/emulator dan uji fungsi sebelum status PASS_RUNTIME.

## Keutamaan pembaikan
- Tambah aset logo nyamuk rasmi yang telah diluluskan (jangan mereka logo gantian).
- Pisahkan controller offline ini daripada worker automatik production; jangan gambarkan sebagai UAPC penuh.
- Sahkan compile Android dan fungsi sebenar sebelum merge PR.
