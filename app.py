from flask import Flask, render_template, request
import requests

app = Flask(__name__)


# Tüm kurları toplu halde çeken yardımcı bir fonksiyon
def tum_kurlari_getir():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    veri = requests.get(url).json()
    usd_try = veri["rates"]["TRY"]
    eur_usd = veri["rates"]["EUR"]
    gbp_usd = veri["rates"]["GBP"]

    # Çapraz kur hesabı (TL bazında)
    return {
        "USD": round(usd_try, 2),
        "EUR": round(usd_try / eur_usd, 2),
        "GBP": round(usd_try / gbp_usd, 2)
    }


@app.route("/", methods=["GET", "POST"])
def index():
    kurlar = tum_kurlari_getir()  # Sağ köşe için kurları her zaman çek
    sonuc = None
    miktar = None
    birim = None

    if request.method == "POST":
        miktar = float(request.form.get("miktar"))
        birim = request.form.get("birim")
        # Seçilen birimin kur değerini kullanıp hesapla
        sonuc = round(miktar * (kurlar[birim] if birim != "USD" else kurlar["USD"]), 2)

    return render_template("index.html", kurlar=kurlar, sonuc=sonuc, miktar=miktar, birim=birim)


if __name__ == "__main__":
    app.run(debug=True)