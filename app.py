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
        # --- 1. KAYNAK: DOVIZ.COM (Temel Kurlar ve Altınlar) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=8)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            return el.text.strip() if el else None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        kurlar["CHF"] = doviz_bul("CHF")
        altin["GRAM"] = doviz_bul("gram-altin")
        altin["CEYREK"] = doviz_bul("ceyrek-altin")
        altin["YARIM"] = doviz_bul("yarim-altin")
        altin["TAM"] = doviz_bul("tam-altin")
        altin["CUMHURIYET"] = doviz_bul("cumhuriyet-altini")
        altin["ATA"] = doviz_bul("ata-altini")

        # --- 2. KAYNAK: MYNET (Japon Yeni) ---
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else "---"
        except:
            kurlar["JPY"] = "---"

        # --- 3. KAYNAK: PARATIC (ONS ALTIN, GÜMÜŞ ONS, PLN) ---
        try:
            res_p_ons = requests.get("https://piyasa.paratic.com/altin/ons/", headers=headers, timeout=5)
            soup_p_ons = BeautifulSoup(res_p_ons.content, "html.parser")
            ons_el = soup_p_ons.find("div", {"class": "price"})
            altin["ONS"] = ons_el.text.strip().replace("$", "").replace(" ", "").split('\n')[0] if ons_el else "---"
        except:
            altin["ONS"] = "---"

        try:
            res_p_gumus = requests.get("https://piyasa.paratic.com/forex/emtia/gumus-ons/", headers=headers, timeout=5)
            soup_p_gumus = BeautifulSoup(res_p_gumus.content, "html.parser")
            gumus_el = soup_p_gumus.find("div", {"class": "price"})
            altin["ONS-GUMUS"] = gumus_el.text.strip().replace("$", "").replace(" ", "").split('\n')[0] if gumus_el else "---"
        except:
            altin["ONS-GUMUS"] = "---"

        try:
            res_p_pln = requests.get("https://piyasa.paratic.com/doviz/polonya-zlotisi/", headers=headers, timeout=5)
            soup_p_pln = BeautifulSoup(res_p_pln.content, "html.parser")
            pln_el = soup_p_pln.find("div", {"class": "price"})
            kurlar["PLN"] = pln_el.text.strip().split('\n')[0] if pln_el else "---"
        except:
            kurlar["PLN"] = "---"

        # --- 4. YEDEKLEME (ALTIN.IN) ---
        if altin.get("ONS-GUMUS") == "---" or not altin.get("ONS-GUMUS"):
            try:
                res_ain = requests.get("https://www.altin.in", headers=headers, timeout=5)
                soup_ain = BeautifulSoup(res_ain.content, "html.parser")
                gumus_yedek = soup_ain.find("dfn", {"id": "dfn_gumus_ons"})
                if gumus_yedek:
                    altin["ONS-GUMUS"] = gumus_yedek.text.strip()
            except:
                pass

        # --- TEMİZLİK VE BELLEK GÜNCELLEME ---
        for d in [kurlar, altin]:
            for k, v in d.items():
                if not v or v == "0" or v == "0,00" or "%" in str(v):
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Genel Hata: {e}")
        return son_veriler.get("kurlar", {}), son_veriler.get("altin", {})

@app.route("/")
def index():
    # ÇÖZÜM BURADA: Render'ın botu kontrol ettiğinde beklemesin diye kazıma işlemini sildik.
    # HTML anında yüklenir, JS arkadan API'ye vurup verileri doldurur.
    return render_template("index.html", kurlar=son_veriler.get("kurlar", {}), altin_fiyatlari=son_veriler.get("altin", {}))

@app.route("/api/fiyatlar")
def api_fiyatlar():
    k, a = verileri_kazi()
    return jsonify({"kurlar": k, "altin": a})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)