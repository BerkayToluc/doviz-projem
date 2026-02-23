import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# API'den verileri çeken fonksiyon
def tum_kurlari_getir():
    api_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(api_url)
        data = response.json()
        return data["rates"]
    except Exception as e:
        print(f"API Hatası: {e}")
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    kurlar = tum_kurlari_getir()
    # Eğer API'den veri gelmezse site çökmesin diye boş değerler
    if not kurlar:
        kurlar = {"USD": 1, "TRY": 0, "EUR": 0, "GBP": 0}

    sonuc = None
    miktar = None
    birim = None

    if request.method == "POST":
        try:
            miktar_raw = request.form.get("miktar")
            if miktar_raw:
                miktar = float(miktar_raw)
                birim = request.form.get("birim")
                if birim in kurlar:
                    sonuc = round(miktar * kurlar[birim], 2)
        except (ValueError, TypeError):
            sonuc = "Lütfen geçerli bir sayı girin."

    return render_template("index.html", kurlar=kurlar, sonuc=sonuc, miktar=miktar, birim=birim)

# RENDER İÇİN KRİTİK AYAR - BURASI ÇOK ÖNEMLİ
if __name__ == "__main__":
    # Render PORT isminde bir değişken gönderir, eğer bulamazsa 5000 kullanır
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)