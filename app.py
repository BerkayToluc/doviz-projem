import os
import time
import requests
import threading
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv

# Loglama yapılandırması (Olası hataları anında görmek için)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- SUPABASE AYARLARI ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VARSAYILAN_PORT = 5000
VERI_YUKLENIYOR = "..."
VERI_YOK = "---"
DUSUK_FIYATLI_SEMBOLLER = ["DOGEUSDT", "XRPUSDT"]

# İdeal Hızımız
CACHE_SURESI = 8
REQUEST_TIMEOUT = 10

TARAYICI_BASLIGI = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

RAM_ACILIS_FIYATLARI = {}
ACILIS_YUKLENDI_MI = False

sonVeriler = {
    "kurlar": {k: VERI_YUKLENIYOR for k in ["USD", "EUR", "GBP", "JPY", "PLN", "CHF", "CAD", "RUB", "SAR"]},
    "altin": {k: VERI_YUKLENIYOR for k in
              ["GRAM", "CEYREK", "YARIM", "TAM", "ATA", "ONS", "ONS-GUMUS", "BRENT", "BAKIR"]},
    "kripto": {k: VERI_YUKLENIYOR for k in ["BTC", "ETH", "SOL", "AVAX", "DOGE", "XRP"]}
}


def fiyatiFormatla(deger, sembol=""):
    if sembol in DUSUK_FIYATLI_SEMBOLLER:
        return "{:.4f}".format(deger).replace('.', ',')
    return "{:,.2f}".format(deger).replace(',', 'X').replace('.', ',').replace('X', '.')


def metniSayiyaCevir(metin):
    try:
        metin = str(metin).replace("₺", "").replace("$", "").replace("TL", "").strip()
        nokta_pos = metin.rfind('.')
        virgul_pos = metin.rfind(',')
        if nokta_pos == -1 and virgul_pos == -1: return float(metin)
        if virgul_pos > nokta_pos:
            return float(metin.replace('.', '').replace(',', '.'))
        else:
            return float(metin.replace(',', ''))
    except:
        return 0.0


def acilis_fiyatlarini_getir():
    global RAM_ACILIS_FIYATLARI, ACILIS_YUKLENDI_MI
    if not ACILIS_YUKLENDI_MI:
        try:
            logger.info("Açılış fiyatları çekiliyor...")
            acilislar_db = supabase.table("gunluk_acilis").select("*").execute().data
            RAM_ACILIS_FIYATLARI = {row["varlik_kodu"]: row["fiyat"] for row in acilislar_db}
            ACILIS_YUKLENDI_MI = True
        except Exception as e:
            pass
    return RAM_ACILIS_FIYATLARI


# ==============================================================
# 🚀 1. MOTOR: TRUNCGIL FINANS API (Bulut Sunucu Engellemez)
# ==============================================================
# ==============================================================
# 🚀 YENİ MOTOR: TRUNCGIL FINANS API (BULUT SUNUCULARI ENGELLEMEZ)
# ==============================================================
def truncgil_piyasa_cek(ham_kurlar_str, ham_altin_str):
    try:
        logger.info("Truncgil API'den veriler çekiliyor (Ban yemez)...")
        url = "https://finans.truncgil.com/today.json"
        r = requests.get(url, headers=TARAYICI_BASLIGI, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200:
            data = r.json()

            # 1. Dövizler
            for kod in ["USD", "EUR", "GBP", "CHF", "CAD", "JPY", "RUB", "SAR"]:
                if kod in data:
                    satis = data[kod].get("Satış") or data[kod].get("satis")
                    if satis: ham_kurlar_str[kod] = satis

            # 2. Altınlar (Gümüş Gram TL olduğu için listeden çıkarıldı, Dolar ONS olarak CNBC'den çekilecek)
            altinlar = {
                "GRAM": "gram-altin",
                "CEYREK": "ceyrek-altin",
                "YARIM": "yarim-altin",
                "TAM": "tam-altin",
                "ATA": "cumhuriyet-altini",
                "ONS": "ons"
            }
            for kod, isim in altinlar.items():
                if isim in data:
                    satis = data[isim].get("Satış") or data[isim].get("satis")
                    if satis: ham_altin_str[kod] = satis

            logger.info("Truncgil verileri başarıyla alındı!")
        else:
            logger.error(f"Truncgil Hata: HTTP {r.status_code}")
    except Exception as e:
        logger.error(f"Truncgil Coktu: {e}")


# ==============================================================
# 🛠 2. MOTOR: EKSİK DÖVİZ TAMAMLAYICI (Ücretsiz API)
# ==============================================================
def eksik_dovizleri_cek(ham_kurlar_str):
    eksik_dovizler = [d for d in ["PLN", "RUB", "SAR", "CAD", "JPY"] if
                      ham_kurlar_str.get(d) == VERI_YOK or d not in ham_kurlar_str]
    if not eksik_dovizler: return

    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            rates = r.json().get("rates", {})
            usd_try = rates.get("TRY")
            if usd_try and usd_try > 0:
                for d in eksik_dovizler:
                    rate_usd = rates.get(d)
                    if rate_usd and rate_usd > 0:
                        val_try = usd_try / rate_usd
                        ham_kurlar_str[d] = "{:.4f}".format(val_try).replace('.', ',')
    except Exception as e:
        logger.error(f"ExchangeRate-API exception: {e}")


# ==============================================================
# 🛢 3. MOTOR: CNBC EMTİA (Brent ve Bakır İçin)
# ==============================================================
def emtia_cnbc_cek(ham_altin_str):
    # Brent Petrol
    if ham_altin_str.get("BRENT", VERI_YOK) == VERI_YOK:
        try:
            r = requests.get("https://www.cnbc.com/quotes/@LCO.1", headers=TARAYICI_BASLIGI, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                match = re.search(r'"last":"([0-9\.]+)"', r.text)
                if match: ham_altin_str["BRENT"] = "{:.2f}".format(float(match.group(1))).replace('.', ',')
        except:
            pass

    # Bakır
    if ham_altin_str.get("BAKIR", VERI_YOK) == VERI_YOK:
        try:
            r = requests.get("https://www.cnbc.com/quotes/@HG.1", headers=TARAYICI_BASLIGI, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                match = re.search(r'"last":"([0-9\.]+)"', r.text)
                if match: ham_altin_str["BAKIR"] = "{:.4f}".format(float(match.group(1))).replace('.', ',')
        except:
            pass

    # Ons Gümüş (Gerçek USD Fiyatı - $76 civarı)
    if ham_altin_str.get("ONS-GUMUS", VERI_YOK) == VERI_YOK:
        try:
            r = requests.get("https://www.cnbc.com/quotes/@SI.1", headers=TARAYICI_BASLIGI, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                match = re.search(r'"last":"([0-9\.]+)"', r.text)
                if match: ham_altin_str["ONS-GUMUS"] = "{:.2f}".format(float(match.group(1))).replace('.', ',')
        except:
            pass


# ==============================================================
# 🪙 4. MOTOR: BINANCE (Kriptolar İçin - Saniyelik)
# ==============================================================
def binance_cek(ham_kripto):
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22,%22AVAXUSDT%22,%22DOGEUSDT%22,%22XRPUSDT%22%5D'
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            for coin in r.json():
                sym = coin["symbol"]
                fiyat = float(coin["price"])
                kod = sym.replace("USDT", "")
                ham_kripto[kod] = fiyatiFormatla(fiyat, sym)
    except Exception as e:
        logger.error(f"Binance exception: {e}")


# ==============================================================
# ANA BİRLEŞTİRİCİ
# ==============================================================
def verileriCek_gercek():
    global sonVeriler

    ham_kurlar_str = {}
    ham_altin_str = {"GRAM": VERI_YOK, "CEYREK": VERI_YOK, "YARIM": VERI_YOK, "TAM": VERI_YOK, "ATA": VERI_YOK,
                     "ONS": VERI_YOK, "ONS-GUMUS": VERI_YOK, "BRENT": VERI_YOK, "BAKIR": VERI_YOK}
    ham_kripto_str = {}

    # Turbo Mod: Truncgil ve Binance'i aynı anda başlat
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_trunc = executor.submit(truncgil_piyasa_cek, ham_kurlar_str, ham_altin_str)
        fut_binance = executor.submit(binance_cek, ham_kripto_str)

        try:
            fut_trunc.result(timeout=REQUEST_TIMEOUT + 1)
        except:
            pass

        try:
            fut_binance.result(timeout=REQUEST_TIMEOUT + 1)
        except:
            pass

    # Eksikler için yedek motorları çalıştır
    eksik_dovizleri_cek(ham_kurlar_str)
    emtia_cnbc_cek(ham_altin_str)

    # Matematik Sağlaması (Eğer Trunçgil'de anlık kopma olursa matematikle hesapla)
    ons_str = ham_altin_str.get("ONS", VERI_YOK)
    usd_str = ham_kurlar_str.get("USD", VERI_YOK)

    if ons_str != VERI_YOK and usd_str != VERI_YOK:
        ons_val = metniSayiyaCevir(ons_str)
        usd_val = metniSayiyaCevir(usd_str)

        if ons_val > 0 and usd_val > 0:
            gram = (ons_val * usd_val) / 31.1034768
            if ham_altin_str.get("GRAM", VERI_YOK) == VERI_YOK: ham_altin_str["GRAM"] = fiyatiFormatla(gram)
            if ham_altin_str.get("CEYREK", VERI_YOK) == VERI_YOK: ham_altin_str["CEYREK"] = fiyatiFormatla(gram * 1.64)
            if ham_altin_str.get("YARIM", VERI_YOK) == VERI_YOK: ham_altin_str["YARIM"] = fiyatiFormatla(gram * 3.28)
            if ham_altin_str.get("TAM", VERI_YOK) == VERI_YOK: ham_altin_str["TAM"] = fiyatiFormatla(gram * 6.56)
            if ham_altin_str.get("ATA", VERI_YOK) == VERI_YOK: ham_altin_str["ATA"] = fiyatiFormatla(gram * 6.78)

    acilis_sozlugu = acilis_fiyatlarini_getir()

    def zenginlestir(ham_veri):
        zengin_veri = {}
        for kod, fiyat_str in ham_veri.items():
            if fiyat_str in [VERI_YUKLENIYOR, VERI_YOK]:
                zengin_veri[kod] = {"fiyat": fiyat_str, "yuzde": 0.0}
                continue
            guncel_deger = metniSayiyaCevir(fiyat_str)
            acilis_degeri = acilis_sozlugu.get(kod)
            yuzde = 0.0
            if acilis_degeri and acilis_degeri > 0:
                yuzde = round(((guncel_deger - acilis_degeri) / acilis_degeri) * 100, 2)
            zengin_veri[kod] = {"fiyat": fiyat_str, "yuzde": yuzde}
        return zengin_veri

    if ham_kurlar_str: sonVeriler["kurlar"] = zenginlestir(ham_kurlar_str)
    if ham_altin_str: sonVeriler["altin"] = zenginlestir(ham_altin_str)
    if ham_kripto_str: sonVeriler["kripto"] = zenginlestir(ham_kripto_str)


def arkaplan_dongusu():
    while True:
        try:
            verileriCek_gercek()
        except Exception as e:
            logger.error(f"Arkaplan döngüsü hatası: {e}")
        time.sleep(CACHE_SURESI)


logger.info("Uygulama başlatılıyor - ilk veri çekimi yapılıyor...")
try:
    verileriCek_gercek()
except Exception as e:
    logger.error(f"İlk veri çekimi hatası: {e}")

# Arka plan motorunu başlat
threading.Thread(target=arkaplan_dongusu, daemon=True).start()


# 🥷 ÖNBELLEK KATİLİ (Tarayıcıyı kandırmak için zorunludur)
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response


@app.route("/api/kaydet-gecmis", methods=["POST"])
def kaydetGecmis():
    try:
        veri = request.json
        kullanici_id = veri.get("kullanici_id")
        bakiye = veri.get("bakiye")
        if kullanici_id and bakiye is not None:
            supabase.table("portfoy_gecmisi").insert({"kullanici_id": kullanici_id, "bakiye": float(bakiye)}).execute()
            return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 400
    return jsonify({"durum": "gecersiz_veri"}), 400


@app.route("/api/gece-tetikleyici")
def geceTetikleyici():
    global RAM_ACILIS_FIYATLARI, ACILIS_YUKLENDI_MI
    try:
        verileriCek_gercek()
        tum_veriler = {**sonVeriler.get("kurlar", {}), **sonVeriler.get("altin", {}), **sonVeriler.get("kripto", {})}
        kayit_listesi, yeni_ram_verisi = [], {}

        for kod, data in tum_veriler.items():
            fiyat_str = data.get("fiyat")
            if fiyat_str and fiyat_str not in [VERI_YUKLENIYOR, VERI_YOK]:
                sayisal_deger = metniSayiyaCevir(fiyat_str)
                kayit_listesi.append({"varlik_kodu": kod, "fiyat": sayisal_deger})
                yeni_ram_verisi[kod] = sayisal_deger

        if kayit_listesi:
            supabase.table("gunluk_acilis").upsert(kayit_listesi).execute()
            RAM_ACILIS_FIYATLARI = yeni_ram_verisi
            ACILIS_YUKLENDI_MI = True
        return jsonify({"durum": "basarili", "mesaj": "Gece 00:00 fiyatları kaydedildi!"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)})


@app.route("/")
def anaSayfa():
    return render_template("index.html")


@app.route("/api/fiyatlar")
def apiFiyatlar():
    return jsonify(sonVeriler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", VARSAYILAN_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)