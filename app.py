import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- HIZLI AÇILIŞ İÇİN BELLEK (CACHE) ---
son_veriler = {"kurlar": {}, "altin": {}}


def verileri_kazi():
    global son_veriler
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    kurlar = {}
    altin = {}

    try:
        # --- 1. KAYNAK: DOVIZ.COM (Dolar, Euro, Gram Altın vb.) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=8)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            return el.text.strip() if el else None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        altin["GRAM"] = doviz_bul("gram-altin")
        altin["CEYREK"] = doviz_bul("ceyrek-altin")
        altin["YARIM"] = doviz_bul("yarim-altin")
        altin["TAM"] = doviz_bul("tam-altin")
        altin["CUMHURIYET"] = doviz_bul("cumhuriyet-altini")
        altin["ATA"] = doviz_bul("ata-altini")

        # --- 2. KAYNAK: MYNET (Sadece Japon Yeni) ---
        # İstediğin gibi JPY'ye dokunmadım
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                if satir:
                    kurlar["JPY"] = satir.find_all("td")[2].text.strip()
        except:
            kurlar["JPY"] = "---"

        # --- 3. ONS VE PLN (PARATIC'TEN NOKTA ATIŞI) ---

        # ONS ALTIN
        try:
            res_p_ons = requests.get("https://piyasa.paratic.com/altin/ons/", headers=headers, timeout=5)
            soup_p_ons = BeautifulSoup(res_p_ons.content, "html.parser")
            ons_el = soup_p_ons.find("div", {"class": "price"})
            # Fiyatı al, doları at, sadece ilk sayı kısmını tut
            altin["ONS"] = ons_el.text.strip().replace("$", "").replace(" ", "").split('\n')[0] if ons_el else "---"
        except:
            altin["ONS"] = "---"

        # POLONYA ZLOTİSİ (PLN)
        try:
            res_p_pln = requests.get("https://piyasa.paratic.com/doviz/polonya-zlotisi/", headers=headers, timeout=5)
            soup_p_pln = BeautifulSoup(res_p_pln.content, "html.parser")
            pln_el = soup_p_pln.find("div", {"class": "price"})
            kurlar["PLN"] = pln_el.text.strip().split('\n')[0] if pln_el else "---"
        except:
            kurlar["PLN"] = "---"

        # --- TEMİZLİK VE BELLEK GÜNCELLEME ---
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0" or "%" in str(v):
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Hata: {e}")
        return son_veriler.get("kurlar", {}), son_veriler.get("altin", {})


@app.route("/")
def index():
    if son_veriler["kurlar"]:
        k, a = son_veriler["kurlar"], son_veriler["altin"]
    else:
        k, a = verileri_kazi()
    return render_template("index.html", kurlar=k, altin_fiyatlari=a)


@app.route("/api/fiyatlar")
def api_fiyatlar():
    k, a = verileri_kazi()
    return jsonify({"kurlar": k, "altin": a})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)