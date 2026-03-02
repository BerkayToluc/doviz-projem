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
        # --- 1. KAYNAK: DOVIZ.COM (Sadece Ana Kurlar ve Gram Altın İçin) ---
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

        # --- 2. KAYNAK: CANLI ALTIN FİYATLARI (Doviz.com'da eksik olan altınlar için) ---
        try:
            res_altin = requests.get("https://canlialtinfiyatlari.com/", headers=headers, timeout=8)
            soup_altin = BeautifulSoup(res_altin.content, "html.parser")

            def altin_sec(aranan_isim):
                # İçinde 'Çeyrek' vb. geçen metni bul
                isim_hucresi = soup_altin.find(["td", "a", "div"], string=lambda text: text and aranan_isim in text)
                if isim_hucresi:
                    # O ismin bulunduğu satırı (tr) tespit et
                    satir = isim_hucresi.find_parent("tr")
                    if satir:
                        hucreler = satir.find_all("td")
                        # 2. veya 1. indexteki fiyatı al (Satış/Alış)
                        if len(hucreler) >= 2:
                            index = 2 if len(hucreler) > 2 else 1
                            # İçindeki gereksiz 'TL' yazılarını temizle
                            fiyat = hucreler[index].text.replace("TL", "").strip()
                            return fiyat if fiyat else None
                return None

            altin["CEYREK"] = altin_sec("Çeyrek")
            altin["YARIM"] = altin_sec("Yarım")
            altin["TAM"] = altin_sec("Tam")
            altin["CUMHURIYET"] = altin_sec("Cumhuriyet")
            altin["ATA"] = altin_sec("Ata")
        except Exception as e:
            print(f"Altın Tablosu Çekilemedi: {e}")

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
            altin["ONS-GUMUS"] = gumus_el.text.strip().replace("$", "").replace(" ", "").split('\n')[
                0] if gumus_el else "---"
        except:
            altin["ONS-GUMUS"] = "---"

        try:
            res_p_pln = requests.get("https://piyasa.paratic.com/doviz/polonya-zlotisi/", headers=headers, timeout=5)
            soup_p_pln = BeautifulSoup(res_p_pln.content, "html.parser")
            pln_el = soup_p_pln.find("div", {"class": "price"})
            kurlar["PLN"] = pln_el.text.strip().split('\n')[0].replace('.', ',') if pln_el else "---"
        except:
            kurlar["PLN"] = "---"

        try:
            res_p_chf = requests.get("https://piyasa.paratic.com/doviz/isvicre-frangi/", headers=headers, timeout=5)
            soup_p_chf = BeautifulSoup(res_p_chf.content, "html.parser")
            chf_el = soup_p_chf.find("div", {"class": "price"})
            kurlar["CHF"] = chf_el.text.strip().split('\n')[0].replace('.', ',') if chf_el else "---"
        except:
            kurlar["CHF"] = "---"

        # --- 5. YEDEKLEME (ALTIN.IN) ---
        if not altin.get("ONS-GUMUS") or altin["ONS-GUMUS"] == "---":
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
            # Sözlüğü güncellerken hata almamak için list(d.items()) kullanıyoruz
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
    # Eğer bellek boşsa bir kereye mahsus veriyi çek
    if not son_veriler["kurlar"]:
        verileri_kazi()

    return render_template("index.html",
                           kurlar=son_veriler["kurlar"],
                           altin_fiyatlari=son_veriler["altin"])


@app.route("/api/fiyatlar")
def api_fiyatlar():
    k, a = verileri_kazi()
    return jsonify({"kurlar": k, "altin": a})


if __name__ == "__main__":
    # Uygulama başlar başlamaz ilk veriyi çek
    try:
        verileri_kazi()
    except:
        pass

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)