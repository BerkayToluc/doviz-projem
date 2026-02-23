import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)


def verileri_getir():
    api_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(api_url)
        data = response.json()
        oranlar = data["rates"]
        usd_try = oranlar.get("TRY", 0)

        # Tüm birimlerin TL karşılığını hassas hesaplıyoruz
        kurlar = {
            "USD": round(usd_try, 2),
            "EUR": round(usd_try / oranlar["EUR"], 2) if "EUR" in oranlar else 0,
            "GBP": round(usd_try / oranlar["GBP"], 2) if "GBP" in oranlar else 0,
            "JPY": round(usd_try / oranlar["JPY"], 4) if "JPY" in oranlar else 0,
            "PLN": round(usd_try / oranlar["PLN"], 2) if "PLN" in oranlar else 0
        }

        # Altın (Gram altın piyasa fiyatına en yakın hesaplama)
        ons_fiyati = 1 / oranlar["XAU"] if "XAU" in oranlar else 2030
        gram_altin = round((ons_fiyati / 31.1035) * usd_try, 2)

        altin_fiyatlari = {
            "GRAM": gram_altin,
            "CEYREK": round(gram_altin * 1.63, 2),  # Saf altın karşılığı (yaklaşık)
            "YARIM": round(gram_altin * 3.26, 2),
            "TAM": round(gram_altin * 6.52, 2),
            "ONS": round(ons_fiyati, 2)
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
                doviz_sonuc = round(miktar * kurlar[birim], 2)
            elif form_tipi == "altin":
                a_miktar = float(request.form.get("altin_miktari", 0))
                a_turu = request.form.get("altin_turu")
                altin_sonuc = round(a_miktar * altin_fiyatlari[a_turu], 2)
        except:
            pass

    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari,
                           doviz_sonuc=doviz_sonuc, altin_sonuc=altin_sonuc, miktar=miktar, birim=birim)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)