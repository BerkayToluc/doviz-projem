import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


def verileri_kazi():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # Ana sayfa
        res = requests.get("https://www.doviz.com", headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        # Altın sayfası (Ons için)
        altin_res = requests.get("https://www.doviz.com/altin", headers=headers, timeout=10)
        altin_soup = BeautifulSoup(altin_res.content, "html.parser")

        def bul(s, key):
            el = s.find("span", {"data-socket-key": key})
            return el.text.strip() if el else "0"

        kurlar = {
            "USD": bul(soup, "USD"),
            "EUR": bul(soup, "EUR"),
            "GBP": bul(soup, "GBP"),
            "JPY": bul(soup, "JPY"),
            "PLN": bul(soup, "PLN")
        }
        altin = {
            "GRAM": bul(soup, "gram-altin"),
            "ONS": bul(altin_soup, "ons-altin"),
            "CEYREK": bul(soup, "ceyrek-altin"),
            "YARIM": bul(soup, "yarim-altin"),
            "TAM": bul(soup, "tam-altin"),
            "CUMHURIYET": bul(soup, "cumhuriyet-altini"),
            "ATA": bul(soup, "ata-altini")
        }
        return kurlar, altin
    except Exception as e:
        print(f"Scraper hatası: {e}")
        return {"USD": "0", "EUR": "0", "GBP": "0", "JPY": "0", "PLN": "0"}, {"GRAM": "0", "ONS": "0"}


@app.route("/")
def index():
    kurlar, altin_fiyatlari = verileri_kazi()
    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari)


@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})


if __name__ == "__main__":
    # Render için gerekli port ayarı
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)