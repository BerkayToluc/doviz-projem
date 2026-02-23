import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


def verileri_kazi():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # Ana Sayfa Verileri (Dolar, Euro, Gram)
        url = "https://www.doviz.com"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        def bul(key):
            el = soup.find("span", {"data-socket-key": key})
            return el.text.strip() if el else "0"

        # Ons Altın için özel olarak kendi sayfasına gidiyoruz (Garanti olsun)
        ons_url = "https://www.doviz.com/altin/ons-altin"
        ons_res = requests.get(ons_url, headers=headers, timeout=10)
        ons_soup = BeautifulSoup(ons_res.content, "html.parser")
        ons_el = ons_soup.find("span", {"data-socket-key": "ons-altin"})
        ons_deger = ons_el.text.strip() if ons_el else "5.154,00"  # Gelmezse senin istediğin rakam

        kurlar = {"USD": bul("USD"), "EUR": bul("EUR"), "GBP": bul("GBP")}
        altin = {"GRAM": bul("gram-altin"), "ONS": ons_deger}

        return kurlar, altin
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return {"USD": "35,50", "EUR": "38,50", "GBP": "45,00"}, {"GRAM": "7.258,00", "ONS": "5.154,00"}


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