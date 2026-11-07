# UAPC NM — Android APK Builder (Public)

Pembina APK asli Android **tanpa Mac**, menggunakan runner GitHub Actions awam. Repositori ini mengandungi **hanya** penjana templat berdikari. Ia tidak mengakses kod, pangkalan data Neon, token atau fail sulit UAPC NM utama.

## Cara bina dari telefon Android

1. Buka [GitHub Actions — Build APK](https://github.com/wafbaiki-debug/UAPC-NM-APK-Builder-Public/actions/workflows/build-android.yml).
2. Tekan **Run workflow**, dan pilih branch **main**.
3. Isi **objective** seperti `Bina aplikasi nota`, dan **app_title** jika mahu.
4. Tekan **Run workflow**. Jika status **Success**, buka run itu dan cari bahagian **Artifacts**.
5. Muat turun **UAPC-NM-Android-APK** ZIP, ekstrak, kemudian pasang **UAPC-NM-Android.apk** pada Android.
6. Uji fungsi **Tambah**, menyimpan rekod, menutup/membuka semula aplikasi dan **Padam rekod**.

## Templat tersedia

| Kata kunci arahan | Fungsi aplikasi |
| --- | --- |
| nota / catatan / memo | Simpan dan padam nota |
| tugasan / tugas / todo | Senarai tugasan dan tanda siap |
| inventori / stok / barang | Rekod barangan/stok |
| perbelanjaan / belanja / bajet | Rekod amaun RM dan jumlah |

Permintaan jenis aplikasi lain ditolak; tiada tuntutan bahawa pembina ini boleh menjana sebarang aplikasi rumit. Fail yang dibina ialah **debug APK** untuk ujian, bukan keluaran Play Store.

## Pemeriksaan automatik

- Ujian penjana untuk empat templat dan kawalan suntikan kod.
- Java 17, Gradle 8.9, Android SDK API 35, Android Gradle Plugin 8.7.3.
- Penghasilan APK sebenar melalui Gradle, bukan mock/simulasi.
- Semakan ZIP CRC, AndroidManifest.xml, classes.dex dan SHA-256.
- APK serta laporan JSON disimpan sebagai GitHub Artifact selama tujuh hari.
- Aplikasi menyimpan data secara setempat dan tidak meminta izin Internet.

**Pemasangan pada telefon sebenar belum terbukti sehingga APK dipasang dan diuji.**

## Keselamatan dan kos

Repositori ini **PUBLIC**. Jangan masukkan maklumat sulit, kata laluan, token, fail pengguna atau objektif projek peribadi ke input workflow kerana sejarah kerja mungkin kelihatan umum. Kod asal UAPC NM utama kekal PRIVATE.

Runner standard GitHub Actions lazimnya percuma untuk repositori awam; kuota, sekatan akaun, dan syarat GitHub masih terpakai. Tiada jadual automatik atau runner 24/7. Aliran sekarang bermula dari pelayar Android; integrasi terus butang UAPC memerlukan sambungan backend berasingan.
