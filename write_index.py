import codecs

html_content = '''<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <title>3T Reader - Trình Ð?c & Ch?nh S?a PDF Tích H?p AI T?i Thu?ng</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-base: #030712;
            --surface: rgba(17, 24, 39, 0.7);
            --surface-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-green: #10b981;
            --gradient-primary: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            --gradient-text: linear-gradient(to right, #60a5fa, #c084fc);
            --glass-bg: rgba(17, 24, 39, 0.7);
        }

        [data-theme="light"] {
            --bg-base: #f8fafc;
            --surface: rgba(255, 255, 255, 0.8);
            --surface-border: rgba(0, 0, 0, 0.1);
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --glass-bg: rgba(255, 255, 255, 0.9);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        
        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 40%);
            background-attachment: fixed;
            transition: background-color 0.4s ease, color 0.4s ease;
        }

        h1, h2, h3, .logo { font-family: 'Outfit', sans-serif; }

        .glass {
            background: var(--glass-bg);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid var(--surface-border);
            border-radius: 20px;
            transition: all 0.3s ease;
        }

        /* Navbar */
        nav {
            position: fixed; top: 0; width: 100%; z-index: 1000;
            padding: 20px 0; border-bottom: 1px solid var(--surface-border);
            transition: all 0.3s;
            background: rgba(var(--bg-base), 0.6); backdrop-filter: blur(20px);
        }
        .nav-container { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; padding: 0 24px; }
        .logo { font-size: 26px; font-weight: 800; display: flex; align-items: center; gap: 12px; letter-spacing: -0.5px; }
        .logo i { color: #f40f02; font-size: 30px; }
        .nav-links { display: flex; gap: 32px; align-items: center; }
        .nav-links a { color: var(--text-primary); text-decoration: none; font-weight: 500; font-size: 15px; transition: 0.3s; }
        .nav-links a:hover { color: var(--accent-blue); }

        .theme-toggle {
            background: transparent; border: 1px solid var(--surface-border);
            color: var(--text-primary); font-size: 18px; padding: 8px; 
            border-radius: 50%; width: 40px; height: 40px; cursor: pointer;
            display: flex; align-items: center; justify-content: center; transition: 0.3s;
        }
        .theme-toggle:hover { background: var(--surface-border); }

        /* Hero Section */
        .hero { padding: 160px 24px 100px; text-align: center; max-width: 1000px; margin: 0 auto; position: relative; }
        .hero h1 { font-size: 64px; line-height: 1.1; margin-bottom: 24px; letter-spacing: -2px; }
        .hero h1 span { background: var(--gradient-text); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .hero p { font-size: 20px; color: var(--text-secondary); max-width: 800px; margin: 0 auto 48px; font-weight: 400; }

        /* Download Section */
        .downloads { max-width: 1200px; margin: 0 auto 80px; padding: 0 24px; }
        .dl-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
        .dl-card { 
            padding: 40px 32px; text-align: center; transition: transform 0.3s, box-shadow 0.3s;
            display: flex; flex-direction: column; align-items: center; position: relative; overflow: hidden;
        }
        .dl-card:hover { transform: translateY(-8px); box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
        .dl-icon { font-size: 56px; margin-bottom: 24px; }
        .dl-card h3 { font-size: 24px; margin-bottom: 12px; }
        .dl-card p { color: var(--text-secondary); font-size: 15px; margin-bottom: 32px; flex-grow: 1; }
        .btn-download {
            display: inline-flex; align-items: center; gap: 12px; padding: 16px 32px;
            border-radius: 12px; font-weight: 600; font-size: 16px; text-decoration: none;
            transition: all 0.3s; border: none; cursor: pointer; width: 100%; justify-content: center;
        }
        .btn-win { background: var(--gradient-primary); color: white; box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3); }
        .btn-win:hover { box-shadow: 0 12px 32px rgba(59, 130, 246, 0.5); transform: scale(1.02); }
        .btn-mac { background: rgba(139, 92, 246, 0.1); color: var(--accent-purple); border: 1px solid rgba(139, 92, 246, 0.3); }
        .btn-mac:hover { background: rgba(139, 92, 246, 0.2); border-color: rgba(139, 92, 246, 0.5); transform: scale(1.02); }
        .btn-port { background: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .btn-port:hover { background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.5); transform: scale(1.02); }
        .dl-badge {
            position: absolute; top: 20px; right: 20px; background: rgba(59,130,246,0.2); 
            color: #3b82f6; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;
        }

        /* Features */
        .section-title { text-align: center; font-size: 48px; margin-bottom: 64px; letter-spacing: -1px; }
        .features { padding: 100px 24px; max-width: 1200px; margin: 0 auto; }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 32px; }
        .feature-card { padding: 40px; border-radius: 24px; transition: 0.3s; }
        .feature-card:hover { transform: translateY(-5px); }
        .feature-icon { 
            width: 64px; height: 64px; border-radius: 16px; background: rgba(59, 130, 246, 0.1);
            display: flex; align-items: center; justify-content: center; font-size: 28px; color: var(--accent-blue); margin-bottom: 24px;
        }
        .feature-card h3 { font-size: 22px; margin-bottom: 16px; }
        .feature-card p { color: var(--text-secondary); }

        /* Pricing Section */
        .pricing { padding: 80px 24px; max-width: 1000px; margin: 0 auto; }
        .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 32px; }
        .pricing-card { padding: 48px 40px; border-radius: 24px; display: flex; flex-direction: column; position: relative; }
        .pricing-card h3 { font-size: 24px; margin-bottom: 16px; }
        .price { font-size: 48px; font-weight: 800; font-family: 'Outfit'; margin-bottom: 8px; }
        .price span { font-size: 16px; font-weight: 400; color: var(--text-secondary); font-family: 'Inter'; }
        .plan-features { list-style: none; margin: 32px 0; flex-grow: 1; }
        .plan-features li { margin-bottom: 16px; display: flex; align-items: center; gap: 12px; color: var(--text-primary); }
        .plan-features i.fa-check { color: var(--accent-green); }
        .plan-features i.fa-xmark { color: #ef4444; }
        .badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: var(--gradient-primary); color: white; padding: 6px 16px; border-radius: 20px; font-size: 12px; font-weight: 700; white-space: nowrap; }
        .premium-card { border: 2px solid var(--accent-blue); transform: scale(1.05); }

        /* FAQ Section */
        .faq { padding: 80px 24px; max-width: 800px; margin: 0 auto; }
        .faq-item { margin-bottom: 24px; border-bottom: 1px solid var(--surface-border); padding-bottom: 24px; }
        .faq-item h4 { font-size: 20px; margin-bottom: 12px; color: var(--text-primary); }
        .faq-item p { color: var(--text-secondary); }

        footer { text-align: center; padding: 60px 24px; border-top: 1px solid var(--surface-border); margin-top: 60px; }
        
        @media (max-width: 768px) {
            .dl-grid, .pricing-grid { grid-template-columns: 1fr; }
            .hero h1 { font-size: 42px; }
            .nav-links { display: none; }
            .premium-card { transform: scale(1); }
        }
    </style>
</head>
<body>

    <nav id="navbar">
        <div class="nav-container">
            <div class="logo"><i class="fa-solid fa-file-pdf"></i> 3T Reader</div>
            <div class="nav-links">
                <a href="#features">Tính nang</a>
                <a href="#pricing">B?ng giá</a>
                <a href="#faq">FAQ</a>
                <a href="/admin" style="background: rgba(128,128,128,0.1); padding: 8px 20px; border-radius: 20px; border: 1px solid var(--surface-border);">Qu?n tr? h? th?ng</a>
                <button class="theme-toggle" id="themeToggle" title="Chuy?n ch? d? Sáng/T?i">
                    <i class="fa-solid fa-moon"></i>
                </button>
            </div>
        </div>
    </nav>

    <section class="hero">
        <h1>Trình Ð?c & Ch?nh S?a PDF<br><span>M?nh M? Dành Cho Ngu?i Vi?t</span></h1>
        <p>Ph?n m?m PDF siêu mu?t mà, h? tr? Ký s? USB Token hàng lo?t, Nh?n di?n ch? OCR ti?ng Vi?t chính xác 99%, và Tr? lý AI tích h?p. Hoàn toàn mi?n phí các tính nang co b?n.</p>
    </section>

    <section class="downloads">
        <div class="dl-grid">
            <!-- Windows Installer -->
            <div class="dl-card glass">
                <div class="dl-badge">Ph? bi?n nh?t</div>
                <div class="dl-icon" style="color: #00a4ef;"><i class="fa-brands fa-windows"></i></div>
                <h3>B?n Cài Ð?t Windows</h3>
                <p>T? d?ng cài d?t d?y d? thu vi?n AI và C++ c?n thi?t. Khuyên dùng cho máy tính cá nhân và van phòng.</p>
                <a href="/downloads/Setup_3T_Reader_v1.0.18.exe" class="btn-download btn-win">
                    <i class="fa-solid fa-download"></i> T?i Cho Windows
                </a>
                <div style="margin-top: 16px; font-size: 13px; color: var(--text-secondary);">H? tr? Windows 10, 11 (64-bit)</div>
            </div>

            <!-- Windows Portable -->
            <div class="dl-card glass">
                <div class="dl-icon" style="color: #10b981;"><i class="fa-solid fa-bolt"></i></div>
                <h3>B?n Portable (Ch?y Ngay)</h3>
                <p>Không c?n cài d?t, không c?n quy?n Admin. Gi?i nén ra USB là có th? mang di s? d?ng trên b?t k? máy tính nào.</p>
                <a href="/downloads/3TReader-1.0.18-win-portable.zip" class="btn-download btn-port">
                    <i class="fa-solid fa-file-zipper"></i> T?i B?n Portable
                </a>
                <div style="margin-top: 16px; font-size: 13px; color: var(--text-secondary);">File ZIP - Ch? c?n gi?i nén và ch?y</div>
            </div>

            <!-- macOS -->
            <div class="dl-card glass">
                <div class="dl-icon" style="color: var(--text-primary);"><i class="fa-brands fa-apple"></i></div>
                <h3>Phiên B?n macOS</h3>
                <p>Ðu?c t?i uu hóa d?c bi?t cho chip Apple Silicon (M1/M2/M3) và màn hình Retina. Ho?t d?ng siêu mu?t mà.</p>
                <a href="/downloads/3TReader-1.0.0-mac.dmg" class="btn-download btn-mac">
                    <i class="fa-brands fa-apple"></i> T?i Cho macOS
                </a>
                <div style="margin-top: 16px; font-size: 13px; color: var(--text-secondary);">H? tr? macOS 12.0 tr? lên</div>
            </div>
        </div>
    </section>

    <section id="features" class="features">
        <h2 class="section-title">H? Sinh Thái Tính Nang Ð?nh Cao</h2>
        <div class="feature-grid">
            <div class="feature-card glass">
                <div class="feature-icon"><i class="fa-solid fa-file-signature"></i></div>
                <h3>Ký S? Hàng Lo?t (Batch Sign)</h3>
                <p>Ký hàng tram file PDF cùng lúc b?ng USB Token. H? tr? xác th?c eIDAS, PAdES v?i d? b?o m?t cao nh?t, phù h?p cho doanh nghi?p.</p>
            </div>
            <div class="feature-card glass">
                <div class="feature-icon"><i class="fa-solid fa-eye"></i></div>
                <h3>OCR Ti?ng Vi?t Chính Xác 99%</h3>
                <p>Bi?n file PDF ?nh, tài li?u scan thành van b?n có th? tìm ki?m, copy/paste du?c. Công ngh? AI t?i uu riêng cho phông ch? ti?ng Vi?t.</p>
            </div>
            <div class="feature-card glass">
                <div class="feature-icon"><i class="fa-solid fa-language"></i></div>
                <h3>Tr? Lý AI & D?ch Thu?t</h3>
                <p>Bôi den b?t k? do?n van b?n nào d? AI d?ch ngay l?p t?c. Ho?c b?n có th? "chat" v?i tài li?u d? h?i dáp thông tin siêu t?c.</p>
            </div>
            <div class="feature-card glass">
                <div class="feature-icon" style="color: #f59e0b;"><i class="fa-solid fa-gauge-high"></i></div>
                <h3>Hi?u Nang C++ Ð?nh Cao</h3>
                <p>Lõi x? lý PySide6 & MuPDF cho phép m? các file PDF b?n v? k? thu?t n?ng hàng GB siêu mu?t mà, không bao gi? gi?t lag.</p>
            </div>
        </div>
    </section>

    <section id="pricing" class="pricing">
        <h2 class="section-title">B?ng Giá Linh Ho?t</h2>
        <div class="pricing-grid">
            <div class="pricing-card glass">
                <h3>Phiên B?n Mi?n Phí</h3>
                <div class="price">0d<span>/ vinh vi?n</span></div>
                <p style="color: var(--text-secondary); margin-bottom: 24px;">Ph?c v? nhu c?u d?c, in ?n co b?n cho cá nhân.</p>
                <ul class="plan-features">
                    <li><i class="fa-solid fa-check"></i> Ð?c tài li?u PDF siêu mu?t</li>
                    <li><i class="fa-solid fa-check"></i> T?o ghi chú (Highlight, Text)</li>
                    <li><i class="fa-solid fa-check"></i> In ?n tài li?u ch?t lu?ng cao</li>
                    <li style="opacity: 0.4"><i class="fa-solid fa-xmark"></i> Không có Ký s? USB Token</li>
                    <li style="opacity: 0.4"><i class="fa-solid fa-xmark"></i> Không có Tính nang AI & OCR</li>
                </ul>
                <a href="#download" class="btn-download btn-port">T?i V? Ngay</a>
            </div>

            <div class="pricing-card glass premium-card">
                <div class="badge">Ð? XU?T CHO DOANH NGHI?P</div>
                <h3 style="color: var(--accent-blue);">Phiên B?n Cao C?p</h3>
                <div class="price">Liên h?<span>/ license</span></div>
                <p style="color: var(--text-secondary); margin-bottom: 24px;">M? khóa s?c m?nh AI và nang su?t t?i da.</p>
                <ul class="plan-features">
                    <li><i class="fa-solid fa-check"></i> <b>M?i tính nang c?a Mi?n Phí</b></li>
                    <li><i class="fa-solid fa-check"></i> Ký s? USB Token hàng lo?t</li>
                    <li><i class="fa-solid fa-check"></i> Nh?n d?ng ch? Scan (OCR) 99%</li>
                    <li><i class="fa-solid fa-check"></i> Chat v?i Tài li?u b?ng AI</li>
                    <li><i class="fa-solid fa-check"></i> D?ch thu?t AI t? d?ng</li>
                    <li><i class="fa-solid fa-check"></i> H? tr? k? thu?t 24/7</li>
                </ul>
                <button onclick="alert('Vui lòng liên h? Hotline: 09xx.xxx.xxx ho?c Email: contact@3tcomputer.com d? d?t mua b?n quy?n')" class="btn-download btn-win">Liên H? Mua Key</button>
            </div>
        </div>
    </section>

    <section id="faq" class="faq">
        <h2 class="section-title" style="font-size: 36px; margin-bottom: 40px;">Câu H?i Thu?ng G?p</h2>
        <div class="faq-item">
            <h4>B?n Portable khác gì b?n Cài d?t?</h4>
            <p>B?n Portable là b?n du?c dóng gói s?n thành 1 file ZIP duy nh?t. B?n ch? c?n t?i v?, gi?i nén và m? file ch?y mà không c?n c?p quy?n Administrator. R?t ti?n l?i d? chép vào USB mang di s? d?ng trên các máy tính khác nhau.</p>
        </div>
        <div class="faq-item">
            <h4>Ph?n m?m có d?c du?c file PDF b?n v? n?ng không?</h4>
            <p>Hoàn toàn có th?! Ðu?c xây d?ng trên lõi C++ và engine MuPDF n?i ti?ng, 3T Reader có th? m? các file b?n v? thi?t k? n?ng hàng Gigabyte ch? trong vài giây, mu?t mà hon nhi?u so v?i các ph?n m?m n?n web.</p>
        </div>
        <div class="faq-item">
            <h4>D? li?u AI và OCR c?a tôi có du?c b?o m?t?</h4>
            <p>3T Reader cam k?t tuân th? nghiêm ng?t chu?n b?o m?t. Quá trình phân tích AI và nh?n di?n OCR s? không luu tr? d? li?u tài li?u c?a b?n trên máy ch? sau khi quá trình x? lý hoàn t?t.</p>
        </div>
    </section>

    <footer>
        <div class="logo" style="justify-content: center; margin-bottom: 24px;">
            <i class="fa-solid fa-file-pdf"></i> 3T Reader
        </div>
        <p style="color: var(--text-secondary);">&copy; 2026 3T Computer. Ð?c quy?n phát tri?n.</p>
    </footer>

    <script>
        // Navbar scroll effect
        window.addEventListener('scroll', () => {
            const nav = document.getElementById('navbar');
            if (window.scrollY > 50) nav.classList.add('scrolled');
            else nav.classList.remove('scrolled');
        });

        // Theme Toggle Logic
        const themeToggle = document.getElementById('themeToggle');
        const icon = themeToggle.querySelector('i');
        const root = document.documentElement;
        
        // Check local storage for theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            root.setAttribute('data-theme', 'light');
            icon.classList.replace('fa-moon', 'fa-sun');
        }

        themeToggle.addEventListener('click', () => {
            if (root.getAttribute('data-theme') === 'light') {
                root.removeAttribute('data-theme');
                localStorage.setItem('theme', 'dark');
                icon.classList.replace('fa-sun', 'fa-moon');
            } else {
                root.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
                icon.classList.replace('fa-moon', 'fa-sun');
            }
        });
    </script>
</body>
</html>
'''

with codecs.open('C:/Users/HieuPC/Desktop/3T_Reader_Phase1_Win/static/index.html', 'w', 'utf-8') as f:
    f.write(html_content)
