<div align="center">

# AutoScribe v1.7.2

**سرورها و پروتکل‌هایی از Windscribe را پیدا کنید که واقعاً روی شبکهٔ شما کار می‌کنند.**

[English](README.md) · **فارسی** · [Русский](README.ru.md)

</div>

---

<div dir="rtl">

AutoScribe یک برنامهٔ دسکتاپ است که **Windscribe CLI** رسمی را به‌جای شما اجرا می‌کند. این برنامه سرورها، پروتکل‌ها و پورت‌هایی را که انتخاب کرده‌ید یکی‌یکی امتحان می‌کند، به هر کدام وصل می‌شود، پینگ، درصد از دست رفتن بسته‌ها (packet loss) و باز شدن واقعی وب (HTTP/HTTPS) را از داخل تونل اندازه می‌گیرد و بهترین ترکیب‌ها را رتبه‌بندی می‌کند.

## قابلیت‌های جدید در نسخهٔ 1.7.2

- **یادگیری هوشمند از فیدبک فایروال (AI Adaptive Learning)** – موتور سبک و بدون نیاز به کتابخانهٔ خارجی (`ai_engine.py`) شامل تحلیل‌گر شبکه (`NetworkProfiler`)، تست سریع پورت (`SocketProber`)، دسته‌بندی خطاهای DPI (`FailureClassifier`) و زمان‌بند هوشمند Thompson Sampling Bandit.
- **خلبان خودکار (AI Auto-Pilot)** – انتخاب و ارتقای خودکار استراتژی ضدسانسور و اولویت پورت‌ها متناسب با شرایط شبکه.
- **تست پایداری ضد DPI و تست سرعت (Speed Burst)** – باز نگه داشتن تونل و بررسی چندمرحله‌ای برای تشخیص قطعی‌های کاذب (Delayed DPI Reset) همراه با تست دانلود ۱۵۰ کیلوبایتی برای تشخیص خفگی ترافیک.
- **نگهبان اتصال خودکار (Auto-Failover Watchdog)** – بررسی مداوم اتصال VPN هر ۲۵ ثانیه و چرخش خودکار IP یا سوئیچ به مسیر پشتیبان در صورت قطع یا فریز شدن تونل.
- **گزارش هوشمند عیب‌یابی (AI Diagnostic Snapshot)** – تولید و کپی خروجی ساختاریافته برای تحلیل در ChatGPT/Gemini/Claude و اعمال مستقیم تنظیمات پیشنهادی.

## سایر امکانات

- **هدف‌گیری دقیق نودها و گزینهٔ «یک سرور از هر شهر»**
- **فیلتر «فقط سرورهای رایگان»** با نمایش برچسب `[رایگان]`
- **گزینهٔ «حفظ فایروال Windscribe»** بین تست‌ها
- **بررسی اتصال وب (HTTP/Web Check)** در کنار پینگ ICMP
- **تب «عیب‌یاب لاگ» (Diagnostics)** برای بررسی `config/log.bin` و `config.ovpn`
- **پروفایل آمادهٔ `Iran Anti-DPI`** در فایل `config.json`
- **پشتیبانی کامل از سه زبان** انگلیسی، فارسی (راست‌به‌چپ) و روسی

## پیش‌نیازها و اجرا

- **ویندوز ۱۰ یا ۱۱** (یا لینوکس و مک در صورت وجود `windscribe-cli` در `PATH`)
- **پایتون 3.9 یا جدیدتر** همراه با Tkinter و بستهٔ `customtkinter`
- **برنامهٔ دسکتاپ Windscribe** که وارد حساب کاربری شده باشید (`C:\Program Files\Windscribe\windscribe-cli.exe`)

</div>

```bash
pip install -r requirements.txt
python main.py
```

<div dir="rtl">

در ویندوز می‌توانید مستقیماً فایل `run_autoscribe.bat` را اجرا کنید.

## ساخت فایل اجرایی (.exe)

فایل `build_standalone_exe.bat` را اجرا کنید یا از دستور زیر استفاده کنید:

</div>

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --noconsole --name AutoScribe --collect-data customtkinter main.py
```

<div dir="rtl">

فایل‌های `locations.json` و `config.json` را در کنار `AutoScribe.exe` قرار دهید.

</div>
