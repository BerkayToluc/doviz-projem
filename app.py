import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)


# Verileri API'den çeken ana fonksiyon
def verileri_getir():
    # Döviz ve Altın (XAU) verileri için USD tabanlı çekiyoruz
    api_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(api_url)
        data = response.json()
        oranlar = data["rates"]
        try_degeri = oranlar.get("TRY", 0)

        # Döviz Kurları (1 Birim = Kaç TL?)
        kurlar = {
            "USD": round(try_degeri, 2),
            "EUR": round(try_degeri / oranlar["EUR"], 2) if "EUR" in oranlar else 0,
            "GBP": round(try_degeri / oranlar["GBP"], 2) if "GBP" in oranlar else 0,
            "JPY": round(try_degeri / oranlar["JPY"], 4) if "JPY" in oranlar else 0,
            "PLN": round(try_degeri / oranlar["PLN"], 2) if "PLN" in oranlar else 0
        }

        # Altın Hesaplamaları (XAU ons fiyatıdır)
        # Ons değerini API'den alıyoruz (1 / XAU_orani = Ons Fiyatı)
        ons_fiyati = 1 / oranlar["XAU"] if "XAU" in oranlar else 2030
        gram_altin = round((ons_fiyati / 31.1035) * try_degeri, 2)

        altin_fiyatlari = {
            "GRAM": gram_altin,
            "CEYREK": round(gram_altin * 1.75, 2),
            "YARIM": round(gram_altin * 3.50, 2),
            "TAM": round(gram_altin * 7.00, 2),
            "ONS": round(ons_fiyati, 2)
        }

        return kurlar, altin_fiyatlari
    except Exception as e:
        print(f"Veri çekme hatası: {e}")
        return {"USD": 0, "EUR": 0, "GBP": 0, "JPY": 0, "PLN": 0}, {"GRAM": 0, "ONS": 0}


@app.route("/", methods=["GET", "POST"])
def index():
    # Sayfa her yüklendiğinde güncel verileri al
    kurlar, altin_fiyatlari = verileri_getir()

    # Değişkenleri en başta tanımlıyoruz (UnboundLocalError hatasını önlemek için)
    doviz_sonuc = None
    altin_sonuc = None
    miktar = None
    birim = None
    altin_miktari = None
    altin_turu = None

    if request.method == "POST":
        form_tipi = request.form.get("form_tipi")

        try:
            # Döviz Formu Gönderildiyse
            if form_tipi == "doviz":
                miktar_raw = request.form.get("miktar")
                if miktar_raw:
                    miktar = float(miktar_raw)
                    birim = request.form.get("birim")
                    if birim in kurlar:
                        doviz_sonuc = round(miktar * kurlar[birim], 2)

            # Altın Formu Gönderildiyse
            elif form_tipi == "altin":
                altin_miktari_raw = request.form.get("altin_miktari")
                if altin_miktari_raw:
                    altin_miktari = float(altin_miktari_raw)
                    altin_turu = request.form.get("altin_turu")
                    if altin_turu in altin_fiyatlari:
                        altin_sonuc = round(altin_miktari * altin_fiyatlari[altin_turu], 2)
        except Exception as e:
            print(f"Form işleme hatası: {e}")

    # Tüm değişkenleri HTML'e gönder
    return render_template("index.html",
                           kurlar=kurlar,
                           altin_fiyatlari=altin_fiyatlari,
                           doviz_sonuc=doviz_sonuc,
                           altin_sonuc=altin_sonuc,
                           miktar=miktar,
                           birim=birim)


# Render.com için port ayarı
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)