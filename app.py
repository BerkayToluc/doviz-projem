import os
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

def verileri_kazi():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        url = "https://www.doviz.com"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")

        def deger_al(anahtar):
            el = soup.find("span", {"data-socket-key": anahtar})
            if el:
                return el.text.strip()
            return "0"

        # Verileri çekiyoruz
        usd = deger_al("USD")
        eur = deger_al("EUR")
        gbp = deger_al("GBP")
        gram = deger_al("gram-altin")
        ons = deger_al("ons-altin")

        kurlar = {"USD": usd, "EUR": eur, "GBP": gbp}
        altin = {"GRAM": gram, "ONS": ons}
        return kurlar, altin
    except Exception as e:
        print(f"Hata: {e}")
        return {"USD": "35,50", "EUR": "38,50", "GBP": "45,00"}, {"GRAM": "7.258,00", "ONS": "5.154,00"}

@app.route("/", methods=["GET", "POST"])
def index():
    kurlar, altin_fiyatlari = verileri_kazi()
    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari)

# JAVASCRIPT'İN 10 SANİYEDE BİR ÇALACAĞI KAPI
@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)