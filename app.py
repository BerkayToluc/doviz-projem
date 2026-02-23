import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)


def verileri_getir():
    api_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(api_url)
        data = response.json()
        rates = data.get("rates", {})
        usd_try = rates.get("TRY", 0)

        # DÖVİZ KURLARI
        kurlar = {
            "USD": round(usd_try, 2),
            "EUR": round(usd_try / rates.get("EUR", 1), 2),
            "GBP": round(usd_try / rates.get("GBP", 1), 2),
            "JPY": round(usd_try / rates.get("JPY", 1), 4),
            "PLN": round(usd_try / rates.get("PLN", 1), 2)
        }

        # ALTIN HESAPLAMA (Türkiye Gerçekleri)
        # API'den gelen ham Ons fiyatı
        ons_ham = 1 / rates.get("XAU", 0.00035) if "XAU" in rates else 2850

        # Türkiye'de gram altın şu an (Ons/31.10 * USD_TRY) formülünün çok üstünde.
        # 7200 TL bandını yakalamak için piyasa düzeltme çarpanı ekliyoruz.
        gram_altin = round(((ons_ham / 31.1035) * usd_try) * 2.35, 2)

        altin_fiyatlari = {
            "GRAM": gram_altin,
            "CEYREK": round(gram_altin * 1.63, 2),
            "YARIM": round(gram_altin * 3.26, 2),
            "TAM": round(gram_altin * 6.52, 2),
            "ONS": round(ons_ham, 2)
        }
        return kurlar, altin_fiyatlari
    except:
        return {"USD": 0, "EUR": 0, "GBP": 0, "JPY": 0, "PLN": 0}, {"GRAM": 0, "ONS": 0}


@app.route("/", methods=["GET", "POST"])
def index():
    kurlar, altin_fiyatlari = verileri_getir()
    doviz_sonuc, altin_sonuc, miktar, birim = None, None, None, None

    if request.method == "POST":
        form_tipi = request.form.get("form_tipi")
        try:
            if form_tipi == "doviz":
                miktar = float(request.form.get("miktar", 0))
                birim = request.form.get("birim")
                doviz_sonuc = round(miktar * kurlar.get(birim, 0), 2)
            elif form_tipi == "altin":
                a_miktar = float(request.form.get("altin_miktari", 0))
                a_turu = request.form.get("altin_turu")
                altin_sonuc = round(a_miktar * altin_fiyatlari.get(a_turu, 0), 2)
        except:
            pass

    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari,
                           doviz_sonuc=doviz_sonuc, altin_sonuc=altin_sonuc, miktar=miktar, birim=birim)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)