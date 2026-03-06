import os
import requests
from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

son_veriler = {"kurlar": {}, "altin": {}}


def verileri_kazi():
    global son_veriler
    # Daha profesyonel ve güncel bir kimlik
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    kurlar = {}
    altin = {}

    try:
        # --- 1. KAYNAK: DOVIZ.COM (Dolar, Euro, Gram Altın - Zaten Çalışıyor) ---
        res_doviz = requests.get("https://www.doviz.com", headers=headers, timeout=10)
        soup_doviz = BeautifulSoup(res_doviz.content, "html.parser")

        def doviz_bul(key):
            el = soup_doviz.find("span", {"data-socket-key": key})
            return el.text.strip() if el else None

        kurlar["USD"] = doviz_bul("USD")
        kurlar["EUR"] = doviz_bul("EUR")
        kurlar["GBP"] = doviz_bul("GBP")
        altin["GRAM"] = doviz_bul("gram-altin")

        # --- 2. KAYNAK: HAREM ALTIN (ÇEYREK, YARIM, ATA İÇİN YENİ KAYNAK) ---
        try:
            res_harem = requests.get("https://www.haremaltin.com/canli-piyasalar/", headers=headers, timeout=10)
            soup_harem = BeautifulSoup(res_harem.content, "html.parser")

            # Harem Altın'da veriler genelde liste içindedir
            def harem_bul(turu):
                # Önce tüm liste öğelerini bulalım
                items = soup_harem.find_all("li")
                for item in items:
                    name = item.find("span", {"class": "name"})
                    if name and turu.lower() in name.text.lower():
                        price = item.find("span", {"class": "price"})
                        return price.text.strip() if price else None
                return None

            altin["CEYREK"] = harem_bul("Çeyrek")
            altin["YARIM"] = harem_bul("Yarım")
            altin["TAM"] = harem_bul("Tam")
            altin["ATA"] = harem_bul("Ata")
            altin["CUMHURIYET"] = harem_bul("Cumhuriyet")

            print("Harem Altın Verileri Çekildi!")
        except Exception as e:
            print(f"Harem Altın Hatası: {e}")

        # --- 3. KAYNAK: MYNET (Japon Yeni) ---
        try:
            res_m = requests.get("https://finans.mynet.com/doviz/", headers=headers, timeout=10)
            soup_m = BeautifulSoup(res_m.content, "html.parser")
            link = soup_m.find("a", href=lambda x: x and "japon-yeni" in x)
            if link:
                satir = link.find_parent("tr")
                kurlar["JPY"] = satir.find_all("td")[2].text.strip() if satir else "---"
        except:
            kurlar["JPY"] = "---"

        # --- 4. KAYNAK: PARATIC (Ons, Gümüş vb. - Çalışanlar kalsın) ---
        def paratic_cek(path):
            try:
                res = requests.get(f"https://piyasa.paratic.com/{path}", headers=headers, timeout=8)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    el = soup.find("div", {"class": "price"})
                    return el.text.strip().replace("$", "").split('\n')[0] if el else "---"
                return "---"
            except:
                return "---"

        altin["ONS"] = paratic_cek("altin/ons/")
        altin["ONS-GUMUS"] = paratic_cek("forex/emtia/gumus-ons/")
        kurlar["PLN"] = paratic_cek("doviz/polonya-zlotisi/").replace('.', ',')
        kurlar["CHF"] = paratic_cek("doviz/isvicre-frangi/").replace('.', ',')

        # --- TEMİZLİK ---
        for d in [kurlar, altin]:
            for k, v in list(d.items()):
                if v is None or v == "" or v == "0" or v == "---":
                    d[k] = "---"

        son_veriler["kurlar"] = kurlar
        son_veriler["altin"] = altin
        return kurlar, altin

    except Exception as e:
        print(f"Genel Kazıma Hatası: {e}")
        return son_veriler["kurlar"], son_veriler["altin"]


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