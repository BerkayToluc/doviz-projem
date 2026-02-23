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
        # --- 1. KAYNAK: DOVIZ.COM (Standart Birimler) ---
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

        # --- 2. KAYNAK: MYNET FİNANS (Sadece JPY, PLN ve ONS) ---
        res_mynet = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
        soup_mynet = BeautifulSoup(res_mynet.content, "html.parser")

        def mynet_cek(id_parcasi):
            satir = soup_mynet.find("tr", {"id": lambda x: x and id_parcasi in x})
            if satir:
                hucreler = satir.find_all("td")
                return hucreler[2].text.strip() if len(hucreler) > 2 else None
            return None

        # Sorun çıkaranları Mynet'ten alıyoruz
        kurlar["JPY"] = mynet_cek("japon-yeni")
        kurlar["PLN"] = mynet_cek("polonya-zlotisi")

        # ONS Altın için Mynet Altın sayfasına hızlıca bakıyoruz
        res_m_altin = requests.get("https://finans.mynet.com/altin/", headers=headers, timeout=8)
        soup_m_altin = BeautifulSoup(res_m_altin.content, "html.parser")

        def mynet_altin_cek(id_parcasi):
            satir = soup_m_altin.find("tr", {"id": lambda x: x and id_parcasi in x})
            if satir:
                hucreler = satir.find_all("td")
                return hucreler[2].text.strip() if len(hucreler) > 2 else None
            return None

        altin["ONS"] = mynet_altin_cek("ons-altin")

        # --- TEMİZLİK ---
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0":
                    d[k] = "---"

        return kurlar, altin

    except Exception as e:
        print(f"Hata: {e}")
        return {"USD": "---"}, {"GRAM": "---"}


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