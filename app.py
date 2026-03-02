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
        # --- 1. KAYNAK: DOVIZ.COM (Dövizler ve Gram Altın) ---
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

        # --- 2. KAYNAK: PARATIC (TEK İSTEKLE TÜM ALTINLAR - 403 ÇÖZÜMÜ) ---
        try:
            # Tek tek sayfalara gitmek yerine ana listeye gidiyoruz
            url_altin_liste = "https://piyasa.paratic.com/altin/"
            res_liste = requests.get(url_altin_liste, headers=headers, timeout=8)

            if res_liste.status_code == 200:
                soup_altin = BeautifulSoup(res_liste.content, "html.parser")
                rows = soup_altin.find_all("tr")

                for row in rows:
                    name_cell = row.find("td")  # Satırın ilk hücresi isimdir
                    if not name_cell: continue

                    text = name_cell.text.lower()
                    price_div = row.find("div", {"class": "price"})
                    if not price_div: continue

                    fiyat = price_div.text.strip().replace(" ", "").split('\n')[0]

                    if "çeyrek" in text:
                        altin["CEYREK"] = fiyat
                    elif "yarım" in text:
                        altin["YARIM"] = fiyat
                    elif "tam altın" in text:
                        altin["TAM"] = fiyat
                    elif "cumhuriyet" in text:
                        altin["CUMHURIYET"] = fiyat
                    elif "ata altın" in text:
                        altin["ATA"] = fiyat
            else:
                print(f"Altın listesi çekilemedi, Status: {res_liste.status_code}")
        except Exception as e:
            print(f"Paratic Liste Hatası: {e}")

        # --- 3. KAYNAK: MYNET (Japon Yeni) ---
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=8)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else "---"
        except:
            kurlar["JPY"] = "---"

        # --- 4. KAYNAK: PARATIC (ONS ALTIN, GÜMÜŞ ONS, PLN, CHF) ---
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

        # --- 5. YEDEKLEME (ALTIN.IN) ---
        if altin.get("ONS-GUMUS") == "---":
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
            for k, v in list(d.items()):
                if v is None or v == "" or v == "0" or v == "0,00" or v == "None":
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Veri Kazıma Hatası: {e}")
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
    try:
        verileri_kazi()
    except:
        pass
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)