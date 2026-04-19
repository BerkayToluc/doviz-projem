import os
import time
import requests
import threading
import concurrent.futures
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- SUPABASE AYARLARI ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SİSTEM AYARLARI ---
VARSAYILAN_PORT = 5000
VERI_YUKLENIYOR = "..."
VERI_YOK = "---"
DUSUK_FIYATLI_SEMBOLLER = ["DOGEUSDT", "XRPUSDT"]
CACHE_SURESI = 8

TARAYICI_BASLIGI = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': '*/*'
}

# --- YAHOO DEV MOTORU HAFIZASI ---
son_fx_zamani = 0
fx_hafizasi = {}
emtia_hafizasi = {"BRENT": VERI_YOK, "BAKIR": VERI_YOK}

RAM_ACILIS_FIYATLARI = {}
ACILIS_YUKLENDI_MI = False

sonVeriler = {
    "kurlar": {k: VERI_YUKLENIYOR for k in ["USD", "EUR", "GBP", "JPY", "PLN", "CHF", "CAD", "RUB", "SAR"]},
    "altin": {k: VERI_YUKLENIYOR for k in
              ["GRAM", "CEYREK", "YARIM", "TAM", "ATA",  "ONS", "ONS-GUMUS", "BRENT", "BAKIR"]},
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
            acilislar_db = supabase.table("gunluk_acilis").select("*").execute().data
            RAM_ACILIS_FIYATLARI = {row["varlik_kodu"]: row["fiyat"] for row in acilislar_db}
            ACILIS_YUKLENDI_MI = True
        except Exception as e:
            print("Supabase okuma hatası:", e)
    return RAM_ACILIS_FIYATLARI


# ==============================================================
# 1. KAYNAK: YAHOO PARALEL MOTOR (Sadece Döviz, Brent, Bakır)
# ==============================================================
def yahoo_dev_motor():
    global son_fx_zamani, fx_hafizasi, emtia_hafizasi
    su_an = time.time()

    if su_an - son_fx_zamani < 15 and fx_hafizasi:
        return fx_hafizasi, emtia_hafizasi

    yeni_kurlar = {}
    yeni_emtia = {"BRENT": VERI_YOK, "BAKIR": VERI_YOK}

    # Gümüş çıkarıldı, sadece döviz ve petrol/bakır kaldı
    HIZLI_SEMBOLLER = {
        "TRY=X": "USD", "EURTRY=X": "EUR", "GBPTRY=X": "GBP", "CHFTRY=X": "CHF",
        "CADTRY=X": "CAD", "JPYTRY=X": "JPY", "PLNTRY=X": "PLN", "RUBTRY=X": "RUB", "SARTRY=X": "SAR",
        "BZ=F": "BRENT", "HG=F": "BAKIR"
    }

    def _tekil_cek(parca):
        sembol, kod = parca
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sembol}"
            r = requests.get(url, headers=TARAYICI_BASLIGI, timeout=5)
            if r.status_code == 200:
                fiyat = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
                if kod in ["BRENT", "BAKIR"]:
                    if kod == "BRENT":
                        yeni_emtia[kod] = "{:.2f}".format(fiyat).replace('.', ',')
                    elif kod == "BAKIR":
                        yeni_emtia[kod] = "{:.4f}".format(fiyat).replace('.', ',')
                else:
                    yeni_kurlar[kod] = fiyat
        except:
            pass

    with concurrent.futures.ThreadPoolExecutor() as ex:
        ex.map(_tekil_cek, HIZLI_SEMBOLLER.items())

    if yeni_kurlar:
        fx_hafizasi = yeni_kurlar
        emtia_hafizasi = yeni_emtia
        son_fx_zamani = su_an
        print("✅ Yahoo Paralel Motor Çalıştı!")

    return fx_hafizasi, emtia_hafizasi


# ==============================================================
# 2. KAYNAK: DOVİZ.COM MOTORU (Gram Altın, Ons, Ons Gümüş)
# ==============================================================
def doviz_com_cek(ham_altin_str):
    def _cek(url, key):
        try:
            r = requests.get(url, headers=TARAYICI_BASLIGI, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                val = soup.find(attrs={"data-socket-key": key, "data-socket-attr": "s"})
                if val: return val.text.strip()
        except:
            pass
        return None

    # Aynı anda 3 sayfayı hızla çeker
    with concurrent.futures.ThreadPoolExecutor() as ex:
        gelecekler = {
            ex.submit(_cek, "https://altin.doviz.com/gram-altin", "gram-altin"): "GRAM",
            ex.submit(_cek, "https://altin.doviz.com/ons", "ons"): "ONS",
            ex.submit(_cek, "https://altin.doviz.com/ons-gumus", "ons-gumus"): "ONS-GUMUS"
        }
        for future in concurrent.futures.as_completed(gelecekler):
            kod = gelecekler[future]
            sonuc = future.result()
            if sonuc:
                ham_altin_str[kod] = sonuc


# ==============================================================
# 3. KAYNAK: BINANCE (Sadece Kriptolar)
# ==============================================================
def binance_cek(ham_kripto):
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22,%22AVAXUSDT%22,%22DOGEUSDT%22,%22XRPUSDT%22%5D'
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            for coin in r.json():
                sym = coin["symbol"]
                fiyat = float(coin["price"])
                kod = sym.replace("USDT", "")
                ham_kripto[kod] = fiyatiFormatla(fiyat, sym)
    except:
        pass


# ==============================================================
# ANA MOTOR: HARMANLA VE PAKETLE
# ==============================================================
def verileriCek_gercek():
    global sonVeriler
    ham_kurlar_str = {}
    ham_kripto_str = {}

    # 1. Kaynakları Çek
    guncel_fx, guncel_emtia = yahoo_dev_motor()
    binance_cek(ham_kripto_str)

    ham_altin_str = guncel_emtia.copy() if guncel_emtia else {"BRENT": VERI_YOK, "BAKIR": VERI_YOK}

    for kod, fiyat in guncel_fx.items():
        if fiyat > 0:
            ham_kurlar_str[kod] = "{:.4f}".format(fiyat).replace('.', ',')

    # 2. Doviz.com Verilerini Çek
    doviz_com_cek(ham_altin_str)

    # 3. Gerçek Gram Altın Üzerinden Diğer Altınları Hesapla
    gram_str = ham_altin_str.get("GRAM", VERI_YOK)
    if gram_str != VERI_YOK:
        gram_val = metniSayiyaCevir(gram_str)
        if gram_val > 0:
            ham_altin_str["CEYREK"] = fiyatiFormatla(gram_val * 1.64)
            ham_altin_str["YARIM"] = fiyatiFormatla(gram_val * 3.28)
            ham_altin_str["TAM"] = fiyatiFormatla(gram_val * 6.56)
            ham_altin_str["ATA"] = fiyatiFormatla(gram_val * 6.78)


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
    verileriCek_gercek()
    while True:
        time.sleep(CACHE_SURESI)
        verileriCek_gercek()


threading.Thread(target=arkaplan_dongusu, daemon=True).start()


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
        global son_fx_zamani
        son_fx_zamani = 0
        verileriCek_gercek()
        tum_veriler = {**sonVeriler["kurlar"], **sonVeriler["altin"], **sonVeriler["kripto"]}
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
def anaSayfa(): return render_template("index.html")


@app.route("/api/fiyatlar")
def apiFiyatlar(): return jsonify(sonVeriler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", VARSAYILAN_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)