import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


def verileri_kazi():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get("https://www.doviz.com", headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        ons_res = requests.get("https://www.doviz.com/altin/ons-altin", headers=headers, timeout=10)
        ons_soup = BeautifulSoup(ons_res.content, "html.parser")

        def bul(s, key):
            el = s.find("span", {"data-socket-key": key})
            return el.text.strip() if el else "0"

        kurlar = {"USD": bul(soup, "USD"), "EUR": bul(soup, "EUR")}
        altin = {"GRAM": bul(soup, "gram-altin"), "ONS": bul(ons_soup, "ons-altin")}
        return kurlar, altin
    except:
        return {"USD": "35,50", "EUR": "38,50"}, {"GRAM": "7258,00", "ONS": "5154,00"}


@app.route("/")
def index():
    kurlar, altin = verileri_kazi()
    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin)


@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)