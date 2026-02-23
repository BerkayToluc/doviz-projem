import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


def verileri_kazi():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    kurlar = {}
    altin = {}

    try:
        # --- 1. KAYNAK: DOVIZ.COM (USD, EUR, GBP, GRAM VE DIGERLERI) ---
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

        # --- 2. KAYNAK: MYNET FİNANS (SADECE JPY, PLN VE ONS) ---
        # Döviz sayfası (JPY ve PLN için)
        res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
        soup_m = BeautifulSoup(res_m.content, "html.parser")

        def mynet_avla(link_kelimesi):
            # Mynet'te ilgili dövizin linkini bulur
            link = soup_m.find("a", href=lambda x: x and link_kelimesi in x)
            if link:
                # Linkin içinde bulunduğu satırı (tr) bulur
                satir = link.find_parent("tr")
                if satir:
                    hucreler = satir.find_all("td")
                    # 3. hücre (index 2) 'Son' fiyattır
                    return hucreler[2].text.strip()
            return None

        kurlar["JPY"] = mynet_avla("japon-yeni")
        kurlar["PLN"] = mynet_avla("polonya-zlotisi")

        # Altın sayfası (ONS için)
        res_ma = requests.get("https://finans.mynet.com/altin/", headers=headers, timeout=8)
        soup_ma = BeautifulSoup(res_ma.content, "html.parser")

        ons_link = soup_ma.find("a", href=lambda x: x and "ons-altin" in x)
        if ons_link:
            ons_satir = ons_link.find_parent("tr")
            altin["ONS"] = ons_satir.find_all("td")[2].text.strip() if ons_satir else "---"
        else:
            altin["ONS"] = "---"

        # --- TEMİZLİK VE KONTROL ---
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0":
                    d[k] = "---"

        return kurlar, altin

    except Exception as e:
        print(f"Hata: {e}")
        return {"USD": "Hata"}, {"GRAM": "Hata"}


@app.route("/")
def index():
    kurlar, altin_fiyatlari = verileri_kazi()
    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari)


@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)