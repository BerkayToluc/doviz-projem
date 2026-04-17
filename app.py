import os
import time
import requests
import concurrent.futures
import threading
from flask import Flask, render_template, jsonify, request
from bs4 import BeautifulSoup
from supabase import create_client, Client
import cloudscraper
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- SUPABASE ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SİSTEM AYARLARI ---
ISTEK_ZAMAN_ASIMI = 10
VARSAYILAN_PORT = 5000
VERI_YUKLENIYOR = "..."
VERI_YOK = "---"
HTTP_BASARILI = 200
DUSUK_FIYATLI_SEMBOLLER = ["DOGEUSDT", "XRPUSDT"]
CACHE_SURESI = 8

# --- ÖNBELLEK & RAM CACHE ---
RAM_ACILIS_FIYATLARI = {}
ACILIS_YUKLENDI_MI = False

sonVeriler = {
    "kurlar": {"USD": VERI_YUKLENIYOR, "EUR": VERI_YUKLENIYOR, "GBP": VERI_YUKLENIYOR, "JPY": VERI_YUKLENIYOR,
               "PLN": VERI_YUKLENIYOR, "CHF": VERI_YUKLENIYOR, "CAD": VERI_YUKLENIYOR,
               "RUB": VERI_YUKLENIYOR, "SAR": VERI_YUKLENIYOR},
    "altin": {"GRAM": VERI_YUKLENIYOR, "CEYREK": VERI_YUKLENIYOR, "YARIM": VERI_YUKLENIYOR, "TAM": VERI_YUKLENIYOR,
              "ATA": VERI_YUKLENIYOR, "CUMHURIYET": VERI_YUKLENIYOR, "ONS": VERI_YUKLENIYOR,
              "ONS-GUMUS": VERI_YUKLENIYOR, "BRENT": VERI_YUKLENIYOR, "BAKIR": VERI_YUKLENIYOR},
    "kripto": {"BTC": VERI_YUKLENIYOR, "ETH": VERI_YUKLENIYOR, "SOL": VERI_YUKLENIYOR, "AVAX": VERI_YUKLENIYOR,
               "DOGE": VERI_YUKLENIYOR, "XRP": VERI_YUKLENIYOR}
}


# ==============================================================
# YAHOO FİNANS CRUMB + SESSION SİSTEMİ
# ==============================================================

_yf_session = None
_yf_crumb = None
_yf_session_lock = threading.Lock()

# Render'ın IP'sinden daha inandırıcı görünmek için farklı UA'lar
_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
]
_ua_index = 0


def yahoo_session_baslat():
    """Yahoo Finance'a cookie ve crumb alarak oturum açar."""
    global _yf_session, _yf_crumb, _ua_index

    print("[Yahoo] Yeni oturum başlatılıyor...")
    _ua_index = (_ua_index + 1) % len(_USER_AGENTS)

    s = requests.Session()
    s.headers.update({
        'User-Agent': _USER_AGENTS[_ua_index],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    })

    try:
        # 1. Adım: Ana sayfayı ziyaret et — cookie'leri al
        r1 = s.get('https://finance.yahoo.com/', timeout=15)
        print(f"[Yahoo] Ana sayfa: {r1.status_code}")

        time.sleep(1)  # Bot gibi görünmemek için kısa bekleme

        # 2. Adım: CSRF/crumb endpoint'inden crumb al
        # Yahoo'nun kullandığı iki farklı crumb endpoint'i var, ikisini de dene
        crumb = None

        # Yöntem A: consent + crumb endpoint
        r2 = s.get(
            'https://query1.finance.yahoo.com/v1/test/csrfToken',
            headers={'Accept': 'application/json'},
            timeout=10
        )
        if r2.status_code == 200:
            try:
                crumb = r2.json().get('query', {}).get('crumb')
            except Exception:
                pass

        # Yöntem B: Doğrudan crumb endpoint
        if not crumb:
            r3 = s.get(
                'https://query2.finance.yahoo.com/v1/test/csrfToken',
                headers={'Accept': 'application/json'},
                timeout=10
            )
            if r3.status_code == 200:
                try:
                    crumb = r3.json().get('query', {}).get('crumb')
                except Exception:
                    pass

        # Yöntem C: Eski crumb endpoint
        if not crumb:
            r4 = s.get(
                'https://query1.finance.yahoo.com/v1/test/csrfToken',
                params={'formatted': 'true', 'lang': 'en-US', 'region': 'US'},
                timeout=10
            )
            if r4.status_code == 200:
                try:
                    data = r4.json()
                    crumb = data.get('crumb') or data.get('query', {}).get('crumb')
                except Exception:
                    pass

        if crumb:
            _yf_session = s
            _yf_crumb = crumb
            print(f"[Yahoo] Oturum başarılı. Crumb: {crumb[:8]}...")
            return True
        else:
            print("[Yahoo] Crumb alınamadı, session kaydedilmedi.")
            return False

    except Exception as e:
        print(f"[Yahoo] Oturum başlatma hatası: {e}")
        return False


def yahooFinansCek(sembol):
    """Crumb + session kullanarak Yahoo Finance'dan fiyat çeker."""
    global _yf_session, _yf_crumb

    with _yf_session_lock:
        if not _yf_session or not _yf_crumb:
            yahoo_session_baslat()

    if not _yf_session or not _yf_crumb:
        return None

    # query1 ve query2'yi sırayla dene
    for host in ['query1', 'query2']:
        try:
            url = f'https://{host}.finance.yahoo.com/v8/finance/chart/{sembol}'
            r = _yf_session.get(
                url,
                params={
                    'crumb': _yf_crumb,
                    'interval': '1m',
                    'range': '1d',
                    'includePrePost': 'false',
                },
                timeout=ISTEK_ZAMAN_ASIMI
            )

            if r.status_code == 200:
                data = r.json()
                fiyat = data['chart']['result'][0]['meta']['regularMarketPrice']
                return fiyat

            elif r.status_code == 401 or r.status_code == 403:
                # Token geçersiz — oturumu yenile
                print(f"[Yahoo] {r.status_code} hatası, oturum yenileniyor...")
                with _yf_session_lock:
                    _yf_session = None
                    _yf_crumb = None
                    yahoo_session_baslat()
                # Bir kez daha dene
                if _yf_session and _yf_crumb:
                    r2 = _yf_session.get(
                        url,
                        params={'crumb': _yf_crumb},
                        timeout=ISTEK_ZAMAN_ASIMI
                    )
                    if r2.status_code == 200:
                        return r2.json()['chart']['result'][0]['meta']['regularMarketPrice']
                break

        except Exception as e:
            print(f"[Yahoo] {sembol} / {host} hatası: {e}")
            continue

    return None


# ==============================================================
# DÖVİZ + EMTİA ÇEKİMİ (Yahoo crumb sistemi ile)
# ==============================================================

HIZLI_SEMBOLLER = {
    "USDTRY=X": "USDTRY",
    "EURTRY=X": "EURTRY",
    "GBPUSD=X": "GBPUSD",
    "USDCHF=X": "USDCHF",
    "USDCAD=X": "USDCAD",
    "USDJPY=X": "USDJPY",
    "USDPLN=X": "USDPLN",
    "USDRUB=X": "USDRUB",
    "USDSAR=X": "USDSAR",
    "BZ=F":    "BRENT",
    "HG=F":    "BAKIR",
}


def devasaHizliDovizCekimi(kurlar, altin):
    hizli_veriler = {}

    def _cek(parca):
        sembol, kod = parca
        fiyat = yahooFinansCek(sembol)
        if fiyat:
            hizli_veriler[kod] = fiyat
        else:
            print(f"[Yahoo] {sembol} fiyat alınamadı.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        ex.map(_cek, HIZLI_SEMBOLLER.items())

    usd_try = hizli_veriler.get("USDTRY")
    if usd_try:
        kurlar["USD"] = f"{usd_try:.4f}".replace('.', ',')
        if "EURTRY" in hizli_veriler:
            kurlar["EUR"] = f"{hizli_veriler['EURTRY']:.4f}".replace('.', ',')
        if "GBPUSD" in hizli_veriler:
            kurlar["GBP"] = f"{hizli_veriler['GBPUSD'] * usd_try:.4f}".replace('.', ',')
        if "USDCHF" in hizli_veriler:
            kurlar["CHF"] = f"{usd_try / hizli_veriler['USDCHF']:.4f}".replace('.', ',')
        if "USDCAD" in hizli_veriler:
            kurlar["CAD"] = f"{usd_try / hizli_veriler['USDCAD']:.4f}".replace('.', ',')
        if "USDPLN" in hizli_veriler:
            kurlar["PLN"] = f"{usd_try / hizli_veriler['USDPLN']:.4f}".replace('.', ',')
        if "USDJPY" in hizli_veriler:
            kurlar["JPY"] = f"{usd_try / hizli_veriler['USDJPY']:.4f}".replace('.', ',')
        if "USDRUB" in hizli_veriler:
            kurlar["RUB"] = f"{usd_try / hizli_veriler['USDRUB']:.4f}".replace('.', ',')
        if "USDSAR" in hizli_veriler:
            kurlar["SAR"] = f"{usd_try / hizli_veriler['USDSAR']:.4f}".replace('.', ',')
    else:
        print("[Yahoo] USDTRY alınamadı, döviz verileri güncellenemedi.")

    if "BRENT" in hizli_veriler:
        altin["BRENT"] = f"{hizli_veriler['BRENT']:.2f}".replace('.', ',')
    if "BAKIR" in hizli_veriler:
        altin["BAKIR"] = f"{hizli_veriler['BAKIR']:.4f}".replace('.', ',')


# ==============================================================
# ALTIN ÇEKİMİ (Paratic — cloudscraper ile)
# ==============================================================

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})


def paratictenCek(yol):
    try:
        cevap = scraper.get(f"https://piyasa.paratic.com/{yol}", timeout=ISTEK_ZAMAN_ASIMI)
        if cevap.status_code == HTTP_BASARILI:
            sayfa = BeautifulSoup(cevap.content, "html.parser")
            baslik = sayfa.find("h1")
            eleman = baslik.find_next("div", {"class": "price"}) if baslik else sayfa.find("div", {"class": "price"})
            return eleman.text.strip().replace("$", "").split('\n')[0] if eleman else VERI_YOK
        return VERI_YOK
    except:
        return VERI_YOK


def paraticHayaletAltinCek(altin):
    ons_str = paratictenCek("altin/ons/")
    if ons_str != VERI_YOK:
        try:
            altin["ONS"] = fiyatiFormatla(metniSayiyaCevir(ons_str))
        except:
            altin["ONS"] = ons_str

    gumus_str = paratictenCek("forex/emtia/gumus-ons/")
    if gumus_str != VERI_YOK:
        try:
            altin["ONS-GUMUS"] = fiyatiFormatla(metniSayiyaCevir(gumus_str))
        except:
            altin["ONS-GUMUS"] = gumus_str

    gram_str = paratictenCek("altin/gram-altin/")
    if gram_str != VERI_YOK:
        try:
            g_val = metniSayiyaCevir(gram_str)
            altin["GRAM"]       = fiyatiFormatla(g_val)
            altin["CEYREK"]     = fiyatiFormatla(g_val * 1.64)
            altin["YARIM"]      = fiyatiFormatla(g_val * 3.28)
            altin["TAM"]        = fiyatiFormatla(g_val * 6.56)
            altin["ATA"]        = fiyatiFormatla(g_val * 6.78)
            altin["CUMHURIYET"] = fiyatiFormatla(g_val * 6.60)
        except:
            pass


# ==============================================================
# KRİPTO ÇEKİMİ (Binance — değişmedi)
# ==============================================================

def binancedenKriptoVerileriniCek(kripto):
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22,%22AVAXUSDT%22,%22DOGEUSDT%22,%22XRPUSDT%22%5D'
        r = requests.get(url, timeout=ISTEK_ZAMAN_ASIMI)
        if r.status_code == HTTP_BASARILI:
            MAP = {"BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
                   "AVAXUSDT": "AVAX", "DOGEUSDT": "DOGE", "XRPUSDT": "XRP"}
            for coin in r.json():
                kod = MAP.get(coin["symbol"])
                if kod:
                    kripto[kod] = fiyatiFormatla(float(coin["price"]), coin["symbol"])
    except:
        pass


# ==============================================================
# YARDIMCI FONKSİYONLAR
# ==============================================================

def fiyatiFormatla(deger, sembol=""):
    if sembol in DUSUK_FIYATLI_SEMBOLLER:
        return "{:.4f}".format(deger).replace('.', ',')
    return "{:,.2f}".format(deger).replace(',', 'X').replace('.', ',').replace('X', '.')


def metniSayiyaCevir(metin):
    metin = str(metin).replace("₺", "").replace("$", "").replace("TL", "").strip()
    nokta_pos = metin.rfind('.')
    virgul_pos = metin.rfind(',')
    if nokta_pos == -1 and virgul_pos == -1:
        return float(metin)
    if virgul_pos > nokta_pos:
        return float(metin.replace('.', '').replace(',', '.'))
    else:
        return float(metin.replace(',', ''))


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
# ANA VERİ DÖNGÜSÜ
# ==============================================================

def verileriCek_gercek():
    global sonVeriler
    ham_kurlar = {k: VERI_YUKLENIYOR for k in ["USD","EUR","GBP","JPY","PLN","CHF","CAD","RUB","SAR"]}
    ham_altin  = {k: VERI_YUKLENIYOR for k in ["GRAM","CEYREK","YARIM","TAM","ATA","CUMHURIYET","ONS","ONS-GUMUS","BRENT","BAKIR"]}
    ham_kripto = {k: VERI_YUKLENIYOR for k in ["BTC","ETH","SOL","AVAX","DOGE","XRP"]}

    try:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            ex.submit(devasaHizliDovizCekimi, ham_kurlar, ham_altin)
            ex.submit(paraticHayaletAltinCek, ham_altin)
            ex.submit(binancedenKriptoVerileriniCek, ham_kripto)

        acilis_sozlugu = acilis_fiyatlarini_getir()

        def zenginlestir(ham_veri):
            zengin_veri = {}
            for kod, fiyat_str in ham_veri.items():
                if fiyat_str in (VERI_YUKLENIYOR, VERI_YOK):
                    zengin_veri[kod] = {"fiyat": fiyat_str, "yuzde": 0.0}
                    continue
                guncel_deger = metniSayiyaCevir(fiyat_str)
                acilis_degeri = acilis_sozlugu.get(kod)
                yuzde = 0.0
                if acilis_degeri and acilis_degeri > 0:
                    yuzde = round(((guncel_deger - acilis_degeri) / acilis_degeri) * 100, 2)
                zengin_veri[kod] = {"fiyat": fiyat_str, "yuzde": yuzde}
            return zengin_veri

        sonVeriler["kurlar"] = zenginlestir(ham_kurlar)
        sonVeriler["altin"]  = zenginlestir(ham_altin)
        sonVeriler["kripto"] = zenginlestir(ham_kripto)

    except Exception as e:
        print(f"[verileriCek_gercek] Hata: {e}")


def arkaplan_dongusu():
    # Uygulama başlarken önce Yahoo oturumunu aç
    yahoo_session_baslat()
    verileriCek_gercek()

    # Her 8 saatte bir oturumu tazele (crumb expire olabilir)
    oturum_sayaci = 0

    while True:
        time.sleep(CACHE_SURESI)
        oturum_sayaci += 1

        # Her ~1 saat (450 döngü × 8 sn = 3600 sn) oturumu yenile
        if oturum_sayaci >= 450:
            print("[Yahoo] Periyodik oturum yenileme...")
            with _yf_session_lock:
                global _yf_session, _yf_crumb
                _yf_session = None
                _yf_crumb = None
            yahoo_session_baslat()
            oturum_sayaci = 0

        verileriCek_gercek()


threading.Thread(target=arkaplan_dongusu, daemon=True).start()


# ==============================================================
# FLASK ROUTE'LARI
# ==============================================================

@app.route("/api/kaydet-gecmis", methods=["POST"])
def kaydetGecmis():
    try:
        veri = request.json
        kullanici_id = veri.get("kullanici_id")
        bakiye = veri.get("bakiye")
        if kullanici_id and bakiye is not None:
            supabase.table("portfoy_gecmisi").insert({
                "kullanici_id": kullanici_id,
                "bakiye": float(bakiye)
            }).execute()
            return jsonify({"durum": "basarili"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)}), 400
    return jsonify({"durum": "gecersiz_veri"}), 400


@app.route("/api/gece-tetikleyici")
def geceTetikleyici():
    global RAM_ACILIS_FIYATLARI, ACILIS_YUKLENDI_MI
    try:
        ham_kurlar, ham_altin, ham_kripto = {}, {}, {}
        devasaHizliDovizCekimi(ham_kurlar, ham_altin)
        paraticHayaletAltinCek(ham_altin)
        binancedenKriptoVerileriniCek(ham_kripto)

        tum_veriler = {**ham_kurlar, **ham_altin, **ham_kripto}
        kayit_listesi, yeni_ram_verisi = [], {}

        for kod, fiyat_str in tum_veriler.items():
            if fiyat_str and fiyat_str not in (VERI_YUKLENIYOR, VERI_YOK):
                sayisal_deger = metniSayiyaCevir(fiyat_str)
                kayit_listesi.append({"varlik_kodu": kod, "fiyat": sayisal_deger})
                yeni_ram_verisi[kod] = sayisal_deger

        if kayit_listesi:
            supabase.table("gunluk_acilis").upsert(kayit_listesi).execute()
            RAM_ACILIS_FIYATLARI = yeni_ram_verisi
            ACILIS_YUKLENDI_MI = True

        return jsonify({"durum": "basarili", "mesaj": "Gece 00:00 fiyatları güncellendi ve RAM'e alındı!"})
    except Exception as e:
        return jsonify({"durum": "hata", "mesaj": str(e)})


# Crumb durumunu görmek için debug endpoint (isteğe bağlı, sonradan silebilirsin)
@app.route("/api/yahoo-durum")
def yahooDurum():
    return jsonify({
        "session_var_mi": _yf_session is not None,
        "crumb_var_mi": _yf_crumb is not None,
        "crumb_onizleme": _yf_crumb[:8] + "..." if _yf_crumb else None
    })


@app.route("/")
def anaSayfa():
    return render_template("index.html")


@app.route("/api/fiyatlar")
def apiFiyatlar():
    return jsonify(sonVeriler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", VARSAYILAN_PORT))
    app.run(host="0.0.0.0", port=port, debug=False)