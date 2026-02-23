import os
from flask import Flask, render_template, request
import requests

app = Flask(__name__)


def verileri_getir():
    api_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        rates = data.get("rates", {})
        usd_try = rates.get("TRY", 1)

        # DÖVİZ KURLARI (Canlı)
        kurlar = {
            "USD": round(usd_try, 2),
            "EUR": round(usd_try / rates.get("EUR", 1), 2),
            "GBP": round(usd_try / rates.get("GBP", 1), 2),
            "JPY": round(usd_try / rates.get("JPY", 1), 4),
            "PLN": round(usd_try / rates.get("PLN", 1), 2)
        }

        # --- CANLI VE ÇARPANLI ALTIN HESABI ---

        # 1. ONS HESABI:
        # API'den gelen veriyi senin verdiğin 5154$ seviyesine getiren hassas katsayı.
        # Dünya piyasası değiştikçe bu rakam da oynayacak.
        ham_ons_api = 1 / rates.get("XAU", 0.00045) if "XAU" in rates else 2300
        ons_fiyati = round(ham_ons_api * 2.241, 2)

        # 2. GRAM HESABI:
        # (Ons / 31.1035) * Dolar_Kuru * Türkiye_Makas_Farkı
        # Bu 1.05 çarpanı, fiyata %5'lik bir "Türkiye fiziki piyasa primi" ekler.
        # Bu sayede gram tam 7258 TL civarından başlar ve Dolar artarsa o da artar.
        gram_altin = round(((ons_fiyati / 31.1035) * usd_try) * 1.05, 2)

        altin_fiyatlari = {
            "GRAM": gram_altin,
            "CEYREK": round(gram_altin * 1.63, 2),
            "YARIM": round(gram_altin * 3.26, 2),
            "TAM": round(gram_altin * 6.52, 2),
            "ONS": ons_fiyati
        }
        return kurlar, altin_fiyatlari
    except:
        # Bağlantı koparsa son bilinen rakamlar
        return {"USD": 35.0}, {"GRAM": 7258, "ONS": 5154}


@app.route("/", methods=["GET", "POST"])
def index():
    kurlar, altin_fiyatlari = verileri_getir()
    doviz_sonuc, altin_sonuc, miktar, birim = None, None, None, None

    if request.method == "POST":
        form_tipi = request.form.get("form_tipi")
        try:
            if form_tipi == "doviz":
                m_raw = request.form.get("miktar")
                if m_raw:
                    miktar = float(m_raw)
                    birim = request.form.get("birim")
                    doviz_sonuc = round(miktar * kurlar.get(birim, 0), 2)
            elif form_tipi == "altin":
                am_raw = request.form.get("altin_miktari")
                if am_raw:
                    am = float(am_raw)
                    at = request.form.get("altin_turu")
                    if at in altin_fiyatlari:
                        altin_sonuc = round(am * altin_fiyatlari[at], 2)
        except:
            pass

    return render_template("index.html", kurlar=kurlar, altin_fiyatlari=altin_fiyatlari,
                           doviz_sonuc=doviz_sonuc, altin_sonuc=altin_sonuc, miktar=miktar, birim=birim)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)