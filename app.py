import os
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)


def verileri_kazi():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # Ana Sayfa Verileri
        res = requests.get("https://www.doviz.com", headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        # Ons verisi bazen ana sayfada 0 döner, garanti olsun diye kendi sayfasından alıyoruz
        ons_res = requests.get("https://www.doviz.com/altin/ons-altin", headers=headers, timeout=10)
        ons_soup = BeautifulSoup(ons_res.content, "html.parser")

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
            "ONS": bul(ons_soup, "ons-altin"),
            "CEYREK": bul(soup, "ceyrek-altin")
        }
        return kurlar, altin
    except:
        return {"USD": "0"}, {"GRAM": "0"}


@app.route("/", methods=["GET", "POST"])
def index():
    kurlar, altin_fiyatlari = verileri_kazi()
    doviz_sonuc, altin_sonuc, miktar, birim = None, None, None, None

    if request.method == "POST":
        form_tipi = request.form.get("form_tipi")
        try:
            if form_tipi == "doviz":
                miktar = float(request.form.get("miktar"))
                birim = request.form.get("birim")
                kur_val = float(kurlar[birim].replace(".", "").replace(",", "."))
                doviz_sonuc = f"{miktar * kur_val:,.2f}"
            elif form_tipi == "altin":
                am = float(request.form.get("altin_miktari"))
                at = request.form.get("altin_turu")
                # Basit hesaplama: Gram bazlı
                kur_val = float(altin_fiyatlari["GRAM"].replace(".", "").replace(",", "."))
                altin_sonuc = f"{am * kur_val:,.2f}"
        except:
            pass

    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari,
                           doviz_sonuc=doviz_sonuc, altin_sonuc=altin_sonuc, miktar=miktar, birim=birim)


@app.route("/api/fiyatlar")
def api_fiyatlar():
    kurlar, altin = verileri_kazi()
    return jsonify({"kurlar": kurlar, "altin": altin})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)