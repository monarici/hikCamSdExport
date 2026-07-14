# HikExporter - Hikvision SD Kart Video Aktarıcı ve Kurtarıcı

HikExporter, Hikvision IP kameralarının SD kartlarında kullandığı tescilli depolama yapısını çözümleyerek, istediğiniz tarih ve saat aralığındaki video kayıtlarını kayıpsız ve çok hızlı bir şekilde kurtarmanızı ve standart oynatılabilir `.mp4` formatında dışa aktarmanızı sağlayan modern, web tabanlı bir yerel uygulamadır.

---

## 📌 Programın Amacı

Hikvision güvenlik kameraları, SD kartlara kayıt yaparken kartın ömrünü uzatmak ve dosya parçalanmasını (fragmentation) önlemek için özel bir dosya yapısı kullanır. Kart içine `index00.bin` adında bir indeks veritabanı ve `hiv00000.mp4` gibi her biri 256MB boyutunda önceden tahsis edilmiş devasa video dosyaları yazar. 

Bu kartlar bilgisayara takıldığında:
1. Windows veya macOS dosya sistemini tanıyamayabilir ve kartı **biçimlendirmenizi (format)** isteyebilir. **(Kesinlikle biçimlendirmeyin!)**
2. Dosyaları kopyalasanız bile standart medya oynatıcılar (VLC, Windows Media Player vb.) bu `.mp4` dosyalarını doğrudan oynatamaz çünkü bunlar ham MPEG-TS/H.264 paket akışları barındırır ve standart MP4 başlıklarına sahip değillerdir.

**HikExporter**, SD karttaki indeks dosyasını saniyeler içinde tarar, tüm video segmentlerinin haritasını çıkarır ve seçtiğiniz tarih aralığındaki görüntüleri diske kopyalama yükü yaratmadan doğrudan `ffmpeg` boru hattı (piping) üzerinden saniyeler içerisinde kırparak oynatılabilir standart MP4 dosyalarına dönüştürür.

---

## ✨ Özellikler

* **Hızlı Tarama & Analiz**: SD karttaki tüm kayıt dilimlerini (segmentlerini) kronolojik olarak listeler.
* **Görsel Zaman Çizelgesi (Timeline)**: Kaydedilmiş görüntülerin gün içindeki dağılımını grafiksel bir cetvel üzerinde gösterir.
* **Akışlı Kesim (Piping - 0.2 Saniye)**: Devasa 256MB'lık dosyaları diske yazıp okumak yerine, doğrudan Python üzerinden `ffmpeg` stdin'ine borulama yapar. Bu sayede 1 dakikalık bir videoyu dışa aktarmak **0.2 saniyeden kısa sürer**.
* **Önizleme Resimleri (Thumbnails)**: Her kayıt diliminin ilk karesini otomatik olarak ayrıştırarak arayüzde önizleme resmi olarak gösterir.
* **Saat Dilimi Desteği**: Kamera yerel saati ile UTC arasındaki farkları otomatik yönetir.
* **Dahili Medya Oynatıcı**: Kurtarılan videoları doğrudan web arayüzündeki oynatıcıdan izleyebilir ve ardından bilgisayarınıza indirebilirsiniz.

---

## 🛠️ Kurulum ve Çalıştırma

Programın çalışabilmesi için bilgisayarınızda **Python 3** ve **FFmpeg** kurulu olmalıdır.

### 1. Windows Kurulumu
1. **Python Kurulumu**: [Python.org](https://www.python.org/downloads/) adresinden en son Python sürümünü indirin. Yükleyiciyi çalıştırırken alttaki **"Add Python to PATH"** (Python'ı PATH'e ekle) seçeneğini **mutlaka işaretleyin**.
2. **FFmpeg Kurulumu**: 
   * [FFmpeg indirme sayfasından](https://ffmpeg.org/download.html) Windows build'ini indirin ve zip dosyasını çıkarın.
   * `bin` klasörünün içindeki `ffmpeg.exe` ve `ffprobe.exe` dosyalarını projenin ana dizinine (program dosyalarının yanına) kopyalayın VEYA FFmpeg yolunu sistem ortam değişkenlerindeki (PATH) değerlere ekleyin.
3. **Kütüphane Kurulumu**: Komut İstemi'ni (CMD) açın ve şu komutu çalıştırın:
   ```cmd
   pip install flask
   ```
4. **Çalıştırma**: Proje klasöründe CMD açıp şu komutla sunucuyu başlatın:
   ```cmd
   python app.py
   ```

### 2. Linux Kurulumu (Debian/Ubuntu/Pardus vb.)
1. Terminali açın ve gerekli sistem paketlerini yükleyin:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip ffmpeg -y
   ```
2. Flask kütüphanesini kurun (Modern Linux dağıtımları için `--break-system-packages` parametresi gerekebilir):
   ```bash
   pip3 install flask --break-system-packages
   ```
3. Proje dizinine giderek uygulamayı çalıştırın:
   ```bash
   python3 app.py
   ```

### 3. macOS Kurulumu
1. **Homebrew** kullanarak Python ve FFmpeg yükleyin (Eğer Brew kurulu değilse önce terminalden kurun):
   ```bash
   brew install python ffmpeg
   ```
2. Flask kütüphanesini yükleyin:
   ```bash
   pip3 install flask
   ```
3. Proje dizininde terminalden uygulamayı çalıştırın:
   ```bash
   python3 app.py
   ```

---

## 🚀 Nasıl Kullanılır?

1. Uygulamayı başlattıktan sonra tarayıcınızda şu adresi açın:
   [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
2. **Kart Yolu** kısmına SD kartınızın bağlı olduğu sürücü harfini veya bağlama noktasını girin:
   * **Windows**: `E:\` veya `F:\` gibi.
   * **Linux**: `/media/kullanici_adi/sürücü_adi` gibi.
   * **macOS**: `/Volumes/sürücü_adi` gibi.
3. **Zaman Dilimi** kısmını varsayılan olan `0 (Kamera Saat Dilimi)` ayarında bırakın (Hikvision kamera indeksleri doğrudan yerel saati yazar).
4. **Tarat** butonuna basın. Kayıtlar sol tarafa yüklenecek ve zaman çizelgesi çizilecektir.
5. Bir kayıt diliminin üstündeki **Seç** butonuna basarak tarih aralığını otomatik doldurun VEYA sağ panelden kurtarmak istediğiniz özel başlangıç ve bitiş saatlerini girin.
6. **Videoyu Dışarı Aktar (MP4)** butonuna basın.
7. İşlem tamamlandığında video bilgisayarınızın **Downloads (İndirilenler)** klasörüne kaydedilecek ve arayüzdeki "Son Dışarı Aktarılanlar" listesine eklenecektir. Buradaki **Oynat** butonuna basarak tarayıcı içinden videoyu doğrudan izleyebilirsiniz.
