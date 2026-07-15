# HikExporter - Hikvision SD Kart Video Aktarıcı ve Kurtarıcı

HikExporter, Hikvision IP kameralarının SD kartlarında kullandığı tescilli depolama yapısını çözümleyerek, istediğiniz tarih ve saat aralığındaki video kayıtlarını kayıpsız, sıkıştırmasız ve kopyalama hızında (.mp4 formatında) dışa aktarmanızı sağlayan modern, yerel bir uygulamadır.

---

## 📌 Programın Amacı

Hikvision güvenlik kameraları, SD kartlara kayıt yaparken kartın ömrünü uzatmak ve dosya parçalanmasını (fragmentation) önlemek için özel bir dosya yapısı kullanır. Kart içine `index00.bin` adında bir indeks veritabanı ve `hiv00000.mp4` gibi her biri 256MB boyutunda önceden tahsis edilmiş devasa video dosyaları yazar. 

Bu kartlar bilgisayara takıldığında:
1. Windows veya macOS dosya sistemini tanıyamayabilir ve kartı **biçimlendirmenizi (format)** isteyebilir. **(Kesinlikle biçimlendirmeyin!)**
2. Dosyaları kopyalasanız bile standart medya oynatıcılar (VLC, Windows Media Player vb.) bu `.mp4` dosyalarını doğrudan oynatamaz çünkü bunlar ham MPEG-TS/H.264 paket akışları barındırır ve standart MP4 başlıklarına sahip değillerdir.

**HikExporter**, SD karttaki indeks dosyasını saniyeler içinde tarar, tüm video segmentlerinin haritasını çıkarır ve seçtiğiniz tarih aralığındaki görüntüleri diske kopyalama yükü yaratmadan doğrudan `ffmpeg` boru hattı (piping) üzerinden saniyeler içerisinde kırparak oynatılabilir standart MP4 dosyalarına dönüştürür.

---

## ✨ Özellikler

* **Otomatik Kart Algılama**: Sistem `/media`, `/run/media` gibi dizinleri tarayarak bağlı olan Hikvision SD kartını otomatik olarak algılar ve varsayılan yol olarak seçer.
* **Hızlı Dışarı Aktarma (Kayıpsız Paketleme)**: Videoları yeniden kodlamak (transcoding) yerine doğrudan paket kopyalama (stream copy) yöntemiyle standart MP4 kabuğuna sarar. Bu sayede aktarım işlemi **saniyeler içinde, kopyalama hızında** biter ve CPU'yu yormaz.
* **Dilimli Kayıt Yapısı**: Seçilen geniş zaman aralıklarını birleştirmek yerine doğrudan kameranın 256MB'lık doğal sınırlarında tek tek MP4 dosyaları olarak dışarı aktarır. Böylece dosyalar sunucu yükleme sınırlarına (256MB) mükemmel uyum sağlar.
* **Klasör Kopyalama Arayüzü**: Aktarım bittiğinde üretilen dosyaları listeler ve hedef klasör yolunu tek tıkla panoya kopyalamanızı sağlayan kullanıcı dostu bir arayüz sunar.
* **Önizleme Resimleri (Thumbnails)**: Her kayıt diliminin ilk karesini arka planda işlemciyi yormayacak şekilde tek tek (sıralı kilit mekanizmasıyla) oluşturarak arayüzde gösterir.
* **CLI (Komut Satırı) Desteği**: Arayüz kullanmak istemeyenler için bağımsız, sorusuz çalışan `export_cli.py` betiği içerir.

---

## 🛠️ Kurulum ve Çalıştırma

Programın çalışabilmesi için bilgisayarınızda **Python 3** ve **FFmpeg** kurulu olmalıdır.

### 1. Windows Kurulumu
1. **Python Kurulumu**: [Python.org](https://www.python.org/downloads/) adresinden en son Python sürümünü indirin. Yükleyiciyi çalıştırırken alttaki **"Add Python to PATH"** (Python'ı PATH'e ekle) seçeneğini **mutlaka işaretleyin**.
2. **FFmpeg Kurulumu**: 
   * [FFmpeg indirme sayfasından](https://ffmpeg.org/download.html) Windows build'ini indirin ve zip dosyasını çıkarın.
   * `bin` klasörünün içindeki `ffmpeg.exe` ve `ffprobe.exe` dosyalarını projenin ana dizinine (program dosyalarının yanındaki `app.py`nin yanına) kopyalayın.
   * **ÖNEMLİ**: FFmpeg dosyalarını kopyaladıktan sonra, sistemin bu dosyaları görebilmesi için **kullandığınız terminali (CMD/PowerShell), kod editörünü (VS Code vb.) kapatıp açın veya bilgisayarı yeniden başlatın**.
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
2. Flask kütüphanesini kurun:
   ```bash
   pip3 install flask --break-system-packages
   ```
3. Proje dizinine giderek uygulamayı çalıştırın:
   ```bash
   python3 app.py
   ```

---

## 🚀 Çalıştırma Yöntemleri

### Yöntem A: Web Arayüzü (Önerilen)
1. Uygulamayı başlattıktan sonra tarayıcınızda şu adresi açın:
   [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
2. Kart takılıysa otomatik olarak algılanacaktır. Tarat butonuna basın.
3. Kurtarmak istediğiniz zaman aralığını seçin, bir dosya öneki girin ve **Videoyu Dışarı Aktar** butonuna tıklayın.
4. Tamamlandığında açılan pencerede hedef klasör yolunu tek tuşla kopyalayabilir ve dosyaları görebilirsiniz.

### Yöntem B: Komut Satırı Betiği (`export_cli.py`)
Arayüz ve tarayıcı kullanmadan doğrudan terminal üzerinden en yüksek hızda video kopyalamak istiyorsanız:
1. Terminalde proje klasöründeyken şu komutu çalıştırın:
   ```bash
   python3 export_cli.py
   ```
2. Betik sırasıyla şunları soracaktır:
   * **Kamera Medya Klasör Yolu**: Boş bırakırsanız takılı SD kartı otomatik tespit edip seçer.
   * **Başlangıç Tarih ve Saati**: `YYYY-MM-DD HH:MM:SS` formatında (Örn: `2026-06-13 07:00:00`)
   * **Bitiş Tarih ve Saati**: `YYYY-MM-DD HH:MM:SS` formatında (Örn: `2026-06-13 15:00:00`)
   * **Hedef Klasör Yolu**: Dosyaların kaydedileceği konum.
   * **Dosya Önadı (Önek)**: Dosya isimlerinin başına gelecek kelime.
3. Betik saniyeler içinde paralel olarak tüm ilgili segmentleri kopyalayacaktır.
