import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)


# API Fonksiyonu
def verileri_getir():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
        data = response.json()
        rates = data.get("rates", {})
        usd_try = rates.get("TRY", 0)

        kurlar = {
            "USD": round(usd_try, 2),
            "EUR": round(usd_try / rates.get("EUR", 1), 2),
            "GBP": round(usd_try / rates.get("GBP", 1), 2),
            "JPY": round(usd_try / rates.get("JPY", 1), 4),
            "PLN": round(usd_try / rates.get("PLN", 2), 2)
        }

        ons = 1 / rates.get("XAU", 1) if "XAU" in rates else 2030
        gram = round((ons / 31.1035) * usd_try, 2)

        altin = {
            "GRAM": gram,
            "CEYREK": round(gram * 1.63, 2),
            "ONS": round(ons, 2)
        }
        return kurlar, altin
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


# RENDER İÇİN EN KRİTİK NOKTA BURASI
if __name__ == "__main__":
    # 'PORT' değişkenini Render otomatik atar, bulamazsa 10000 kullanırız
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)