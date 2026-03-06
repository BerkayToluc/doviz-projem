import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# BAŞLANGIÇTA VERİLERİ BOŞ TANIMLIYORUZ (Render'ın anında açılması için)
son_veriler = {
    "kurlar": {"USD": "...", "EUR": "...", "GBP": "...", "JPY": "...", "PLN": "...", "CHF": "..."},
    "altin": {"GRAM": "...", "CEYREK": "...", "YARIM": "...", "TAM": "...", "ATA": "...", "CUMHURIYET": "...", "ONS": "...", "ONS-GUMUS": "..."},
    "kripto": {"BTC": "...", "ETH": "...", "DOGE": "..."}
}

def verileri_kazi():
    global son_veriler
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    kurlar = {}
    altin = {}
    kripto = {}

    try:
        # --- 1. KAYNAK: DOVIZ.COM ---
        try:
            res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=5)
            soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")
            def doviz_bul(key):
                el = soup_doviz.find("span", {"data-socket-key": key})
                return el.text.strip() if el else "---"

            kurlar["USD"] = doviz_bul("USD")
            kurlar["EUR"] = doviz_bul("EUR")
            kurlar["GBP"] = doviz_bul("GBP")
            altin["GRAM"] = doviz_bul("gram-altin")
        except: pass

        # --- 2. KAYNAK: TRUNCGIL API ---
        try:
            res_api = requests.get("https://finans.truncgil.com/v3/today.json", timeout=5)
            if res_api.status_code == 200:
                veri = res_api.json()
                altin["CEYREK"] = veri.get("ceyrek-altin", {}).get("Selling", "---")
                altin["YARIM"] = veri.get("yarim-altin", {}).get("Selling", "---")
                altin["TAM"] = veri.get("tam-altin", {}).get("Selling", "---")
                altin["ATA"] = veri.get("ata-altin", {}).get("Selling", "---")
                altin["CUMHURIYET"] = veri.get("cumhuriyet-altini", {}).get("Selling", "---")
        except: pass

        # --- 3. KAYNAK: MYNET ---
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=5)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else "---"
        except: kurlar["JPY"] = "---"

        # --- 4. KAYNAK: PARATIC ---
        def paratic_cek(path):
            try:
                res = requests.get(f"https://piyasa.paratic.com/{path}", headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    el = soup.find("div", {"class": "price"})
                    return el.text.strip().replace("$", "").split('\n')[0] if el else "---"
                return "---"
            except: return "---"

        altin["ONS"] = paratic_cek("altin/ons/")
        altin["ONS-GUMUS"] = paratic_cek("forex/emtia/gumus-ons/")
        kurlar["PLN"] = paratic_cek("doviz/polonya-zlotisi/").replace('.', ',')
        kurlar["CHF"] = paratic_cek("doviz/isvicre-frangi/").replace('.', ',')

        # --- 5. KAYNAK: BINANCE API (KRİPTO PARALAR) ---
        # --- 5. KAYNAK: BINANCE API (KRİPTO VARLIKLAR) ---
        def kripto_cek(symbol):
            try:
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5)
                fiyat = float(res.json()["price"])
                # Dogecoin ve Ripple gibi ucuz coinlerde 4 küsurat gösterilsin
                if symbol in ["DOGEUSDT", "XRPUSDT"]:
                    return "{:.4f}".format(fiyat).replace('.', ',')
                else:
                    return "{:,.2f}".format(fiyat).replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                return "---"

        kripto["BTC"] = kripto_cek("BTCUSDT")
        kripto["ETH"] = kripto_cek("ETHUSDT")
        kripto["SOL"] = kripto_cek("SOLUSDT")
        kripto["AVAX"] = kripto_cek("AVAXUSDT")
        kripto["DOGE"] = kripto_cek("DOGEUSDT")
        kripto["XRP"] = kripto_cek("XRPUSDT")


        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        son_veriler["kripto"] = kripto
        return kurlar, altin, kripto
    except Exception as e:
        print(f"Hata: {e}")
        return son_veriler["kurlar"], son_veriler["altin"], son_veriler["kripto"]

@app.route("/")
def index():
    if son_veriler["kurlar"].get("USD") == "...":
        verileri_kazi()
    return render_template("index.html", kurlar=son_veriler["kurlar"], altin_fiyatlari=son_veriler["altin"], kripto_fiyatlari=son_veriler["kripto"])

@app.route("/api/fiyatlar")
def api_fiyatlar():
    verileri_kazi()
    return jsonify(son_veriler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)