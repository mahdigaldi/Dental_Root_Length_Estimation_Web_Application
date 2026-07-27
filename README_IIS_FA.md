# راه‌اندازی وب‌اپ دندان روی IIS ویندوز سرور

این پوشه `web` یک وب‌اپ مستقل Flask است و برای اجرا روی IIS آماده شده است. پروژه لوکال اصلی لازم نیست روی سرور باشد؛ فقط همین پوشه را روی سرور کپی کن.

## روش پیشنهادی

روش پیشنهادی برای IIS ویندوز سرور:

- IIS + HttpPlatformHandler
- Python virtual environment داخل همین پوشه
- Waitress برای اجرای WSGI app

فایل فعال برای این روش:

- `web.config`
- `server.py`
- `app.py`

## 1. پیش‌نیازهای Windows Server

در Server Manager یا PowerShell این موارد باید نصب باشند:

```powershell
Install-WindowsFeature Web-Server, Web-Static-Content, Web-Default-Doc, Web-Http-Errors, Web-Http-Logging, Web-Request-Monitor, Web-Filtering, Web-Mgmt-Console
```

همچنین Python 3.12 یا Python 3.11 نصب باشد و در دسترس باشد:

```powershell
py -3.12 --version
```

اگر Python 3.12 نداری، Python 3.11 هم قابل استفاده است، ولی هنگام نصب venv دستور را مطابق نسخه خودت تغییر بده.

## 2. نصب HttpPlatformHandler

برای اجرای Flask/Waitress پشت IIS، افزونه HttpPlatformHandler را روی سرور نصب کن.

بعد از نصب، IIS را restart کن:

```powershell
iisreset
```

اگر امکان نصب HttpPlatformHandler نداری، بخش «روش جایگزین FastCGI» را ببین.

## 3. کپی پروژه روی سرور

پوشه `web` را مثلاً اینجا کپی کن:

```text
C:\inetpub\DentalWeb\web
```

داخل این پوشه باید این فایل‌ها وجود داشته باشند:

```text
app.py
server.py
web.config
requirements.txt
models\detector_best.pt
models\cls_d_best.pt
models\cls_e_best.pt
models\alt_length_model.joblib
models\length_bin_mapping.json
models\length_calibration.json
models\alt_calibration.json
```

## 4. ساخت محیط Python و نصب پکیج‌ها

PowerShell را با دسترسی Administrator باز کن:

```powershell
cd C:\inetpub\DentalWeb\web
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

اگر از فایل آماده استفاده می‌کنی:

```powershell
cd C:\inetpub\DentalWeb\web
.\install_iis_windows.ps1 -PythonCommand "py -3.12" -AppPoolName "DentalWeb"
```

## 5. ساخت IIS Site

در IIS Manager:

1. از `Application Pools` یک App Pool بساز با نام `DentalWeb`.
2. گزینه `.NET CLR version` را روی `No Managed Code` بگذار.
3. از `Sites` یک سایت جدید بساز.
4. `Physical path` را روی مسیر زیر بگذار:

```text
C:\inetpub\DentalWeb\web
```

5. Binding را تنظیم کن، مثلاً:

```text
Type: http
Host name: your-domain.com
Port: 80
```

برای HTTPS بعداً certificate دامنه را Bind کن.

## 6. Permission پوشه‌ها

App Pool باید روی این پوشه‌ها دسترسی Modify داشته باشد:

```text
web\logs
web\static\uploads
web\static\outputs
```

اگر App Pool تو `DentalWeb` است:

```powershell
cd C:\inetpub\DentalWeb\web
icacls .\logs /grant "IIS AppPool\DentalWeb:(OI)(CI)M" /T
icacls .\static\uploads /grant "IIS AppPool\DentalWeb:(OI)(CI)M" /T
icacls .\static\outputs /grant "IIS AppPool\DentalWeb:(OI)(CI)M" /T
```

## 7. تست

ابتدا IIS را restart کن:

```powershell
iisreset
```

بعد این آدرس را باز کن:

```text
http://your-domain.com/health
```

باید این خروجی را ببینی:

```json
{"ok": true}
```

بعد صفحه اصلی را باز کن:

```text
http://your-domain.com/
```

یک تصویر رادیوگرافی آپلود کن و روش `Ensemble` را اجرا کن.

## 8. اگر خطا گرفتی

لاگ‌های IIS:

```text
C:\inetpub\logs\LogFiles
```

لاگ Python/Waitress:

```text
C:\inetpub\DentalWeb\web\logs
```

خطاهای رایج:

- `500.19`: معمولاً HttpPlatformHandler نصب نیست یا `web.config` توسط IIS شناخته نمی‌شود.
- `500 Internal Server Error`: پکیج‌ها نصب نیستند، مدل‌ها در `models` نیستند، یا permission پوشه upload/output مشکل دارد.
- `Can't get attribute C3k2`: نسخه `ultralytics` با وزن مدل سازگار نیست. داخل venv همین دستور را بزن:

```powershell
.\.venv\Scripts\python.exe -m pip install ultralytics==8.4.11
```

## 9. روش جایگزین FastCGI

اگر HttpPlatformHandler قابل نصب نبود:

```powershell
.\.venv\Scripts\python.exe -m pip install wfastcgi
.\.venv\Scripts\python.exe -m wfastcgi-enable
```

بعد فایل `web.config.fastcgi.example` را به `web.config` تبدیل کن و مسیرهای مطلق داخل آن را مطابق مسیر سرور خودت اصلاح کن.

در این روش باید این دو مسیر را دقیق جایگزین کنی:

```text
C:\inetpub\DentalWeb\web\.venv\Scripts\python.exe
C:\inetpub\DentalWeb\web\.venv\Lib\site-packages\wfastcgi.py
```

## 10. نکات عملی برای دامنه

- DNS دامنه را به IP سرور وصل کن.
- در IIS Binding سایت، `Host name` را دامنه خودت قرار بده.
- برای HTTPS از IIS Manager یا win-acme گواهی SSL بگیر.
- چون inference مدل سنگین است، روی CPU اولین درخواست ممکن است کند باشد.
- اگر سرور RAM کم دارد، `threads=2` در `server.py` را افزایش نده.
