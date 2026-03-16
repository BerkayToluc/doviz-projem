import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup
from supabase import create_client, Client

# SİHİRLİ DOKUNUŞ: Her şeyi tek bir 'app' objesinde birleştirdik!
app = Flask(__name__, template_folder='templates', static_folder='static')

SUPABASE_URL="https://ebyinbdxwjyhcmivtluq.supabase.co"
SUPABASE_KEY = "ebyinbdxwjyhcmivtluq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ISTEK_ZAMAN_ASIMI = 5
VARSAYILAN_PORT = 5000
VERI_YUKLENIYOR = "..."
VERI_YOK = "---"
HTTP_BASARILI = 200
DUSUK_FIYATLI_SEMBOLLER = ["DOGEUSDT", "XRPUSDT"]

TARAYICI_BASLIGI = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
}

sonVeriler = {
    "kurlar": {"USD": VERI_YUKLENIYOR, "EUR": VERI_YUKLENIYOR, "GBP": VERI_YUKLENIYOR, "JPY": VERI_YUKLENIYOR, "PLN": VERI_YUKLENIYOR, "CHF": VERI_YUKLENIYOR},
    "altin": {"GRAM": VERI_YUKLENIYOR, "CEYREK": VERI_YUKLENIYOR, "YARIM": VERI_YUKLENIYOR, "TAM": VERI_YUKLENIYOR, "ATA": VERI_YUKLENIYOR, "CUMHURIYET": VERI_YUKLENIYOR, "ONS": VERI_YUKLENIYOR, "ONS-GUMUS": VERI_YUKLENIYOR},
    "kripto": {"BTC": VERI_YUKLENIYOR, "ETH": VERI_YUKLENIYOR, "SOL": VERI_YUKLENIYOR, "AVAX": VERI_YUKLENIYOR, "DOGE": VERI_YUKLENIYOR, "XRP": VERI_YUKLENIYOR}
}

def fiyatiFormatla(fiyatDegeri, sembol):
    if sembol in DUSUK_FIYATLI_SEMBOLLER:
        return "{:.4f}".format(fiyatDegeri).replace('.', ',')
    return "{:,.2f}".format(fiyatDegeri).replace(',', 'X').replace('.', ',').replace('X', '.')

def dovizComSayfasindanCek(kurlar, altin):
    try:
        dovizCevap = requests.get("https://www.doviz.com", headers=TARAYICI_BASLIGI, timeout=ISTEK_ZAMAN_ASIMI)
        dovizSayfa = BeautifulSoup(dovizCevap.content, "html.parser")
        def dovizDegeriBul(anahtar):
            eleman = dovizSayfa.find("span", {"data-socket-key": anahtar})
            return eleman.text.strip() if eleman else VERI_YOK
        kurlar["USD"] = dovizDegeriBul("USD")
        kurlar["EUR"] = dovizDegeriBul("EUR")
        kurlar["GBP"] = dovizDegeriBul("GBP")
        altin["GRAM"] = dovizDegeriBul("gram-altin")
    except: pass

def truncgilApisindenCek(altin):
    try:
        apiCevap = requests.get("https://finans.truncgil.com/v3/today.json", timeout=ISTEK_ZAMAN_ASIMI)
        if apiCevap.status_code == HTTP_BASARILI:
            apiVerisi = apiCevap.json()
            altin["CEYREK"] = apiVerisi.get("ceyrek-altin", {}).get("Selling", VERI_YOK)
            altin["YARIM"] = apiVerisi.get("yarim-altin", {}).get("Selling", VERI_YOK)
            altin["TAM"] = apiVerisi.get("tam-altin", {}).get("Selling", VERI_YOK)
            altin["ATA"] = apiVerisi.get("ata-altin", {}).get("Selling", VERI_YOK)
            altin["CUMHURIYET"] = apiVerisi.get("cumhuriyet-altini", {}).get("Selling", VERI_YOK)
    except: pass

def mynetSayfasindenCek(kurlar):
    try:
        mynetCevap = requests.get("https://finans.mynet.com/doviz/", headers=TARAYICI_BASLIGI, timeout=ISTEK_ZAMAN_ASIMI)
        mynetSayfa = BeautifulSoup(mynetCevap.content, "html.parser")
        baglanti = mynetSayfa.find("a", href=lambda x: x and "japon-yeni" in x)
        if baglanti:
            satir = baglanti.find_parent("tr")
            kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else VERI_YOK
    except:
        kurlar["JPY"] = VERI_YOK

def paratictenCek(yol):
    try:
        cevap = requests.get(f"https://piyasa.paratic.com/{yol}", headers=TARAYICI_BASLIGI, timeout=ISTEK_ZAMAN_ASIMI)
        if cevap.status_code == HTTP_BASARILI:
            sayfa = BeautifulSoup(cevap.content, "html.parser")
            eleman = sayfa.find("div", {"class": "price"})
            return eleman.text.strip().replace("$", "").split('\n')[0] if eleman else VERI_YOK
        return VERI_YOK
    except:
        return VERI_YOK

def paraticSayfalarindenCek(kurlar, altin):
    altin["ONS"] = paratictenCek("altin/ons/")
    altin["ONS-GUMUS"] = paratictenCek("forex/emtia/gumus-ons/")
    kurlar["PLN"] = paratictenCek("doviz/polonya-zlotisi/").replace('.', ',')
    kurlar["CHF"] = paratictenCek("doviz/isvicre-frangi/").replace('.', ',')

def kriptoFiyatCek(sembol):
    try:
        cevap = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sembol}", timeout=ISTEK_ZAMAN_ASIMI)
        fiyatDegeri = float(cevap.json()["price"])
        return fiyatiFormatla(fiyatDegeri, sembol)
    except:
        return VERI_YOK

def binancedenKriptoVerileriniCek(kripto):
    kripto["BTC"] = kriptoFiyatCek("BTCUSDT")
    kripto["ETH"] = kriptoFiyatCek("ETHUSDT")
    kripto["SOL"] = kriptoFiyatCek("SOLUSDT")
    kripto["AVAX"] = kriptoFiyatCek("AVAXUSDT")
    kripto["DOGE"] = kriptoFiyatCek("DOGEUSDT")
    kripto["XRP"] = kriptoFiyatCek("XRPUSDT")

def verileriCek():
    global sonVeriler
    kurlar = {}
    altin = {}
    kripto = {}

    try:
        dovizComSayfasindanCek(kurlar, altin)
        truncgilApisindenCek(altin)
        mynetSayfasindenCek(kurlar)
        paraticSayfalarindenCek(kurlar, altin)
        binancedenKriptoVerileriniCek(kripto)

        sonVeriler["kurlar"] = kurlar
        sonVeriler["altin"] = altin
        sonVeriler["kripto"] = kripto
        return kurlar, altin, kripto
    except Exception:
        return sonVeriler["kurlar"], sonVeriler["altin"], sonVeriler["kripto"]

# Rotalar @app.route olarak düzeltildi
@app.route("/")
def anaSayfa():
    if sonVeriler["kurlar"].get("USD") == VERI_YUKLENIYOR:
        verileriCek()
    return render_template("index.html", kurlar=sonVeriler["kurlar"], altin_fiyatlari=sonVeriler["altin"], kripto_fiyatlari=sonVeriler["kripto"])

@app.route("/api/fiyatlar")
def apiFiyatlar():
    verileriCek()
    return jsonify(sonVeriler)

# Çalıştırma komutu app.run olarak düzeltildi
if __name__ == "__main__":
    varsayilanPort = int(os.environ.get("PORT", VARSAYILAN_PORT))
    app.run(host="0.0.0.0", port=varsayilanPort, debug=False)