import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- HIZLI AÇILIŞ İÇİN BELLEK (CACHE) ---
son_veriler = {"kurlar": {}, "altin": {}}

def verileri_kazi():
    global son_veriler
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    kurlar = {}
    altin = {}

    try:
        # --- 1. KAYNAK: DOVIZ.COM (Dolar, Euro, Gram Altın vb.) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=8)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            return el.text.strip() if el else None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        altin["GRAM"] = doviz_bul("gram-altin")
        altin["CEYREK"] = doviz_bul("ceyrek-altin")
        altin["YARIM"] = doviz_bul("yarim-altin")
        altin["TAM"] = doviz_bul("tam-altin")
        altin["CUMHURIYET"] = doviz_bul("cumhuriyet-altini")
        altin["ATA"] = doviz_bul("ata-altini")

        # --- 2. KAYNAK: MYNET (JPY ve PLN için) ---
        res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
        soup_m = BeautifulSoup(res_m.content, "html.parser")

        def mynet_avla(soup_obj, link_kelimesi):
            link = soup_obj.find("a", href=lambda x: x and link_kelimesi in x)
            if link:
                satir = link.find_parent("tr")
                if satir:
                    hucreler = satir.find_all("td")
                    return hucreler[2].text.strip()
            return None

        kurlar["JPY"] = mynet_avla(soup_m, "japon-yeni")
        kurlar["PLN"] = mynet_avla(soup_m, "polonya-zlotisi")

        # --- 3. KAYNAK: BIGPARA (Sadece GÜNCEL ONS ALTIN için) ---
        try:
            res_bigpara = requests.get("https://bigpara.hurriyet.com.tr/altin/ons-altin-fiyati/", headers=headers, timeout=5)
            soup_bp = BeautifulSoup(res_bigpara.content, "html.parser")
            # Bigpara'da canlı fiyat genellikle bu class içindedir
            ons_el = soup_bp.find("span", {"class": "last-price"}) or soup_bp.find("span", {"class": "value"})
            altin["ONS"] = ons_el.text.strip() if ons_el else "---"
        except:
            altin["ONS"] = "---"

        # --- TEMİZLİK VE BELLEK GÜNCELLEME ---
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0":
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Hata: {e}")
        return son_veriler.get("kurlar", {"USD": "Hata"}), son_veriler.get("altin", {"GRAM": "Hata"})

@app.route("/")
def index():
    if son_veriler["kurlar"]:
        kurlar = son_veriler["kurlar"]
        altin_fiyatlari = son_veriler["altin"]
    else:
        kurlar, altin_fiyatlari = verileri_kazi()
    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari)

@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)