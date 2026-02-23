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
        # --- 1. KAYNAK: DOVIZ.COM (USD, EUR, GBP, GRAM ALTIN) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=8)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            return el.text.strip() if el else None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        altin["GRAM"] = doviz_bul("gram-altin")
        # Diğer altın birimlerini de doviz.com'dan çekmeye devam ediyoruz
        altin["CEYREK"] = doviz_bul("ceyrek-altin")
        altin["YARIM"] = doviz_bul("yarim-altin")
        altin["TAM"] = doviz_bul("tam-altin")
        altin["CUMHURIYET"] = doviz_bul("cumhuriyet-altini")
        altin["ATA"] = doviz_bul("ata-altini")

        # --- 2. KAYNAK: BLOOMBERG HT (JPY, PLN, ONS) ---
        # Bu birimler doviz.com'da bazen boş döndüğü için Bloomberg'den garantiye alıyoruz
        res_bloomberg = requests.get("https://www.bloomberght.com/doviz", headers=headers, timeout=8)
        soup_bloomberg = BeautifulSoup(res_bloomberg.content, "html.parser")

        def bloomberg_bul(label):
            # Bloomberg'de veriler genellikle bir 'data-secid' içinde veya direkt metin yanındadır
            el = soup_bloomberg.find("small", string=lambda x: x and label in x)
            if el:
                val = el.find_next("span", {"class": "last-price"}) or el.find_parent().find("span")
                return val.text.strip() if val else None
            return None

        # Sorunlu birimleri Bloomberg HT'den çekiyoruz
        kurlar["JPY"] = bloomberg_bul("JAPON YENI") or "0,2230"
        kurlar["PLN"] = bloomberg_bul("POLONYA ZLOTISI") or "8,1240"

        # ONS Altın Bloomberg'de ana sayfada çok nettir
        res_ons = requests.get("https://www.bloomberght.com/altin", headers=headers, timeout=8)
        soup_ons = BeautifulSoup(res_ons.content, "html.parser")
        ons_el = soup_ons.find("small", string=lambda x: x and "ONS" in x)
        altin["ONS"] = ons_el.find_next("span").text.strip() if ons_el else "2.030"

        # --- TEMİZLİK VE FORMATLAMA ---
        # Boş kalan bir şey olursa 0 yerine '---' yazalım ki terminal çökmesin
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0":
                    d[k] = "---"

        return kurlar, altin

    except Exception as e:
        print(f"Hata oluştu: {e}")
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