import os
import time
import requests
import threading
import re
from flask import Flask, render_template, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv

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
CACHE_SURESI = 8

TARAYICI_BASLIGI = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json'
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
            acilislar_db = supabase.table("gunluk_acilis").select("*").execute().data
            RAM_ACILIS_FIYATLARI = {row["varlik_kodu"]: row["fiyat"] for row in acilislar_db}
            ACILIS_YUKLENDI_MI = True
        except Exception as e:
            pass
    return RAM_ACILIS_FIYATLARI


# ==============================================================
# 1. KAYNAK: TRADINGVIEW ÇİFT MOTOR (Dövizler ve Emtialar - SANİYELİK)
# ER-API TAMAMEN SİLİNDİ!
# ==============================================================
def tradingview_dev_motor(ham_kurlar_str, ham_altin_str):
    # A) FOREX ODASI (Döviz Kurları - Artık 8 Saniyede Bir Canlı!)
    try:
        url_fx = "https://scanner.tradingview.com/forex/scan"
        payload_fx = {
            "symbols": {
                "tickers": [
                    "FX_IDC:USDTRY", "FX_IDC:EURTRY", "FX_IDC:GBPTRY", "FX_IDC:CHFTRY",
                    "FX_IDC:CADTRY", "FX_IDC:JPYTRY", "FX_IDC:PLNTRY", "FX_IDC:RUBTRY", "FX_IDC:SARTRY"
                ]
            },
            "columns": ["close"]
        }
        r_fx = requests.post(url_fx, json=payload_fx, headers=TARAYICI_BASLIGI, timeout=5)
        if r_fx.status_code == 200:
            for item in r_fx.json().get("data", []):
                t = item.get("s", "")
                f = float(item.get("d", [0])[0])
                if f <= 0: continue

                if "USDTRY" in t:
                    ham_kurlar_str["USD"] = "{:.4f}".format(f).replace('.', ',')
                elif "EURTRY" in t:
                    ham_kurlar_str["EUR"] = "{:.4f}".format(f).replace('.', ',')
                elif "GBPTRY" in t:
                    ham_kurlar_str["GBP"] = "{:.4f}".format(f).replace('.', ',')
                elif "CHFTRY" in t:
                    ham_kurlar_str["CHF"] = "{:.4f}".format(f).replace('.', ',')
                elif "CADTRY" in t:
                    ham_kurlar_str["CAD"] = "{:.4f}".format(f).replace('.', ',')
                elif "JPYTRY" in t:
                    ham_kurlar_str["JPY"] = "{:.4f}".format(f).replace('.', ',')
                elif "PLNTRY" in t:
                    ham_kurlar_str["PLN"] = "{:.4f}".format(f).replace('.', ',')
                elif "RUBTRY" in t:
                    ham_kurlar_str["RUB"] = "{:.4f}".format(f).replace('.', ',')
                elif "SARTRY" in t:
                    ham_kurlar_str["SAR"] = "{:.4f}".format(f).replace('.', ',')
    except:
        pass

    # B) CFD ODASI (Altın, Gümüş, Bakır)
    try:
        url_cfd = "https://scanner.tradingview.com/cfd/scan"
        payload_cfd = {
            "symbols": {
                "tickers": [
                    "OANDA:XAUUSD", "FX_IDC:XAUUSD", "TVC:GOLD",
                    "OANDA:XAGUSD", "FX_IDC:XAGUSD", "TVC:SILVER",
                    "TVC:COPPER", "OANDA:XCUUSD", "PEPPERSTONE:XCUUSD"
                ]
            },
            "columns": ["close"]
        }
        r_cfd = requests.post(url_cfd, json=payload_cfd, headers=TARAYICI_BASLIGI, timeout=5)
        if r_cfd.status_code == 200:
            bulunanlar = {"ONS": False, "GUMUS": False, "BAKIR": False}
            for item in r_cfd.json().get("data", []):
                t = item.get("s", "")
                f = float(item.get("d", [0])[0])
                if f <= 0: continue

                if ("XAUUSD" in t or "GOLD" in t) and not bulunanlar["ONS"]:
                    ham_altin_str["ONS"] = "{:.2f}".format(f).replace('.', ',')
                    bulunanlar["ONS"] = True
                elif ("XAGUSD" in t or "SILVER" in t) and not bulunanlar["GUMUS"]:
                    ham_altin_str["ONS-GUMUS"] = fiyatiFormatla(f)
                    bulunanlar["GUMUS"] = True
                elif ("COPPER" in t or "XCUUSD" in t) and not bulunanlar["BAKIR"]:
                    ham_altin_str["BAKIR"] = "{:.4f}".format(f).replace('.', ',')
                    bulunanlar["BAKIR"] = True
    except:
        pass


# ==============================================================
# 2. KAYNAK: BRENT MOTORU (Google Finance & CNBC)
# ==============================================================
def brent_petrol_cek(ham_altin_str):
    if ham_altin_str.get("BRENT", VERI_YOK) != VERI_YOK: return

    try:
        r = requests.get("https://www.google.com/finance/quote/BZW00:NYMEX", headers=TARAYICI_BASLIGI, timeout=4)
        if r.status_code == 200:
            match = re.search(r'class="YMlKec fxKbKc">\$?([0-9,\.]+)', r.text)
            if match:
                val = float(match.group(1).replace(',', ''))
                if val > 0:
                    ham_altin_str["BRENT"] = "{:.2f}".format(val).replace('.', ',')
                    return
    except:
        pass

    try:
        r = requests.get("https://www.cnbc.com/quotes/@LCO.1", headers=TARAYICI_BASLIGI, timeout=4)
        if r.status_code == 200:
            match = re.search(r'"last":"([0-9\.]+)"', r.text)
            if match:
                val = float(match.group(1))
                if val > 0:
                    ham_altin_str["BRENT"] = "{:.2f}".format(val).replace('.', ',')
    except:
        pass


# ==============================================================
# 3. KAYNAK: BINANCE (Kriptolar)
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
    ham_altin_str = {"GRAM": VERI_YOK, "CEYREK": VERI_YOK, "YARIM": VERI_YOK, "TAM": VERI_YOK, "ATA": VERI_YOK,
                     "ONS": VERI_YOK, "ONS-GUMUS": VERI_YOK, "BRENT": VERI_YOK, "BAKIR": VERI_YOK}
    ham_kripto_str = {}

    tradingview_dev_motor(ham_kurlar_str, ham_altin_str)
    brent_petrol_cek(ham_altin_str)
    binance_cek(ham_kripto_str)

    # SAF TRADINGVIEW MATEMATİĞİ (Sıfır Makas, Sadece Spot)
    ons_str = ham_altin_str.get("ONS", VERI_YOK)
    usd_str = ham_kurlar_str.get("USD", VERI_YOK)

    if ons_str != VERI_YOK and usd_str != VERI_YOK:
        ons_val = metniSayiyaCevir(ons_str)
        usd_val = metniSayiyaCevir(usd_str)

        if ons_val > 0 and usd_val > 0:
            gram = (ons_val * usd_val) / 31.1034768
            ham_altin_str["GRAM"] = fiyatiFormatla(gram)
            ham_altin_str["CEYREK"] = fiyatiFormatla(gram * 1.64)
            ham_altin_str["YARIM"] = fiyatiFormatla(gram * 3.28)
            ham_altin_str["TAM"] = fiyatiFormatla(gram * 6.56)
            ham_altin_str["ATA"] = fiyatiFormatla(gram * 6.78)

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
def anaSayfa(): return render_template("index.html")


@app.route("/api/fiyatlar")
def apiFiyatlar(): return jsonify(sonVeriler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", VARSAYILAN_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)