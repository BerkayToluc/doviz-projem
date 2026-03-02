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
        # --- 1. KAYNAK: DOVIZ.COM (Çalışan Kısımlar - Dokunulmadı) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=8)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            if el:
                val = el.text.strip()
                return val if "%" not in val else None
            return None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        altin["GRAM"] = doviz_bul("gram-altin")

        # --- 2. KAYNAK: ALTIN.IN (403 VEREN PARATIC YERİNE BURADAN ALIYORUZ) ---
        try:
            res_ain = requests.get("https://www.altin.in", headers=headers, timeout=8)
            soup_ain = BeautifulSoup(res_ain.content, "html.parser")

            def altin_in_cek(altin_id):
                el = soup_ain.find("dfn", {"id": altin_id})
                return el.text.strip() if el else "---"

            altin["CEYREK"] = altin_in_cek("dfn_ceyrek_altin")
            altin["YARIM"] = altin_in_cek("dfn_yarim_altin")
            altin["TAM"] = altin_in_cek("dfn_tam_altin")
            altin["CUMHURIYET"] = altin_in_cek("dfn_cumhuriyet_altini")
            altin["ATA"] = altin_in_cek("dfn_ata_altin")

            # Eğer Paratic'ten gelen ONS/GÜMÜŞ hata verirse buradan beslenecek
            ons_yedek = altin_in_cek("dfn_ons_altin")
            gumus_yedek = altin_in_cek("dfn_gumus_ons")
        except:
            pass

        # --- 3. KAYNAK: MYNET (Çalışan Kısım - Dokunulmadı) ---
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else "---"
        except:
            kurlar["JPY"] = "---"

        # --- 4. KAYNAK: PARATIC (Sadece çalışan Ons/Döviz kısımları kaldı) ---
        def paratic_tekil_cek(path):
            try:
                res = requests.get(f"https://piyasa.paratic.com/{path}", headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    el = soup.find("div", {"class": "price"})
                    return el.text.strip().replace("$", "").replace(" ", "").split('\n')[0] if el else "---"
                return "---"
            except:
                return "---"

        altin["ONS"] = paratic_tekil_cek("altin/ons/")
        altin["ONS-GUMUS"] = paratic_tekil_cek("forex/emtia/gumus-ons/")
        kurlar["PLN"] = paratic_tekil_cek("doviz/polonya-zlotisi/").replace('.', ',')
        kurlar["CHF"] = paratic_tekil_cek("doviz/isvicre-frangi/").replace('.', ',')

        # Yedekleme Kontrolü (Eğer Paratic 403 verirse Altin.in verisini yaz)
        if altin["ONS"] == "---" and 'ons_yedek' in locals(): altin["ONS"] = ons_yedek
        if altin["ONS-GUMUS"] == "---" and 'gumus_yedek' in locals(): altin["ONS-GUMUS"] = gumus_yedek

        # --- TEMİZLİK ---
        for d in [kurlar, altin]:
            for k, v in list(d.items()):
                if v is None or v == "" or v == "0" or v == "0,00" or v == "None":
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Hata: {e}")
        return son_veriler.get("kurlar", {}), son_veriler.get("altin", {})


@app.route("/")
def index():
    if not son_veriler["kurlar"]:
        verileri_kazi()
    return render_template("index.html", kurlar=son_veriler["kurlar"], altin_fiyatlari=son_veriler["altin"])


@app.route("/api/fiyatlar")
def api_fiyatlar():
    k, a = verileri_kazi()
    return jsonify({"kurlar": k, "altin": a})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)