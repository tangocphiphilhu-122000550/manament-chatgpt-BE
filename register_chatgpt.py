import time
import json
import string
import random
import uuid
import requests as std_requests
from typing import Optional, Dict

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("Vui lòng cài đặt curl_cffi: pip install curl_cffi")
    exit(1)

# Cấu hình API TempMail
TEMPMAIL_API_KEY = "tm_2245ae727b49183440bb41338d249dbafd4a5dc193b343b1" 
TEMPMAIL_BASE_URL = "https://tempmailapi.io.vn/public_api.php"

CHATGPT_BASE = "https://chatgpt.com"
AUTH_BASE = "https://auth.openai.com"

# Danh sách Tên random
FIRST_NAMES = ["James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Lucas", "Mia"]
LAST_NAMES = ["Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor", "Anderson"]

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_device_id():
    return str(uuid.uuid4())

def get_trace_headers():
    trace_id = random.randint(10**17, 10**18 - 1)
    parent_id = random.randint(10**17, 10**18 - 1)
    tid_hex = hex(trace_id)[2:].zfill(16)
    pid_hex = hex(parent_id)[2:].zfill(16)
    uuid_no_dash = str(uuid.uuid4()).replace('-', '')
    
    return {
        'traceparent': f"00-{uuid_no_dash}-{pid_hex}-01",
        'tracestate': 'dd=s:1;o:rum',
        'x-datadog-origin': 'rum',
        'x-datadog-sampling-priority': '1',
        'x-datadog-trace-id': str(trace_id),
        'x-datadog-parent-id': str(parent_id)
    }

class ChatGPTAutoReg:
    def __init__(self, password: str, proxy: Optional[str] = None):
        self.password = password
        self.session = cffi_requests.Session(impersonate="chrome120")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            
        self.device_id = generate_device_id()
        self.auth_session_id = str(uuid.uuid4())
        self.email = ""
        self.name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        year = random.randint(1985, 2002)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        self.birthdate = f"{year}-{month:02d}-{day:02d}"

    def log(self, msg):
        print(f"[RegGPT] {msg}")

    def create_temp_email(self) -> bool:
        try:
            self.log("📋 Đang lấy danh sách domain...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = std_requests.get(f"{TEMPMAIL_BASE_URL}?action=domains", headers=headers, timeout=15)
            data = resp.json()
            if not data.get("success") or not data.get("domains"):
                self.log("❌ Không lấy được domain!")
                return False
            
            domain = random.choice(data["domains"])
            user = generate_random_string(10)
            
            self.log(f"📧 Đang tạo email với cấu trúc {user}@{domain}...")
            create_url = f"{TEMPMAIL_BASE_URL}?action=create&api_key={TEMPMAIL_API_KEY}&domain={domain}&user={user}"
            create_resp = std_requests.get(create_url, headers=headers, timeout=15)
            create_data = create_resp.json()
            
            if not create_data.get("success") or not create_data.get("email"):
                self.log("❌ Không tạo được email!")
                return False
                
            self.email = create_data["email"]
            self.log(f"✅ Đã tạo email: {self.email}")
            return True
        except Exception as e:
            self.log(f"❌ Lỗi TempMail API: {e}")
            return False

    def check_otp(self) -> Optional[str]:
        for attempt in range(1, 25):
            self.log(f"📬 Kiểm tra email lần {attempt}/24...")
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                list_url = f"{TEMPMAIL_BASE_URL}?action=list&api_key={TEMPMAIL_API_KEY}&email={self.email}&limit=5"
                resp = std_requests.get(list_url, headers=headers, timeout=15)
                json_data = resp.json()
                
                if json_data.get("success") and json_data.get("emails"):
                    import re
                    for mail in json_data["emails"]:
                        subject = mail.get("subject", "").lower()
                        body = mail.get("body", "").lower()
                        from_addr = mail.get("from", "").lower()
                        
                        if 'openai' in from_addr or 'chatgpt' in subject:
                            matches = re.findall(r'\b\d{6}\b', subject + " " + body)
                            if matches and matches[0] != '177010':
                                return matches[0]
            except Exception as e:
                self.log(f"⚠ Lỗi check mail: {e}")
            time.sleep(5)
        return None

    def register(self):
        if not self.create_temp_email():
            return False
            
        self.log(f"🔑 Mật khẩu: {self.password}")
        self.log(f"👤 Name: {self.name} | DoB: {self.birthdate}")

        try:
            # Bước 1
            self.log("🌐 Phác thảo session ChatGPT...")
            self.session.get(f"{CHATGPT_BASE}/", headers={"Accept": "text/html"})
            
            # Bước 2
            self.log("🔑 Lấy CSRF Token...")
            csrf_resp = self.session.get(f"{CHATGPT_BASE}/api/auth/csrf", headers={"Accept": "application/json"})
            csrf_token = csrf_resp.json().get("csrfToken")
            if not csrf_token:
                raise Exception("Không lấy được CSRF token")

            # Bước 3
            self.log("🔗 Chuyển hướng xác thực...")
            import urllib.parse
            signin_params = {
                'prompt': 'login',
                'ext-oai-did': self.device_id,
                'auth_session_logging_id': self.auth_session_id,
                'screen_hint': 'login_or_signup',
                'login_hint': self.email,
            }
            signin_body = {
                'callbackUrl': f"{CHATGPT_BASE}/",
                'csrfToken': csrf_token,
                'json': 'true'
            }
            signin_url = f"{CHATGPT_BASE}/api/auth/signin/openai?" + urllib.parse.urlencode(signin_params)
            signin_resp = self.session.post(signin_url, data=signin_body, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": CHATGPT_BASE
            })
            auth_url = signin_resp.json().get("url")
            if not auth_url:
                raise Exception("Không lấy được Auth URL")
                
            self.session.get(auth_url, headers={"Accept": "text/html"})

            # Bước 4
            self.log("📝 Gửi yêu cầu Đăng ký...")
            reg_headers = {"Content-Type": "application/json", "Origin": AUTH_BASE, **get_trace_headers()}
            reg_resp = self.session.post(
                f"{AUTH_BASE}/api/accounts/user/register",
                json={"username": self.email, "password": self.password},
                headers=reg_headers
            )
            if reg_resp.status_code not in [200, 201]:
                self.log(f"⚠ Phản hồi Register: {reg_resp.text}")
            
            # Bước 5
            self.log("📧 Gửi mã OTP...")
            self.session.get(f"{AUTH_BASE}/api/accounts/email-otp/send", headers={"Accept": "text/html"})
            
            # Đọc OTP
            self.log("⏳ Đang chờ mã OTP từ email...")
            otp_code = self.check_otp()
            if not otp_code:
                raise Exception("Trễ thời gian chờ OTP (120s)")
            self.log(f"✅ Mã OTP nhận được: {otp_code}")
            
            # Bước 6
            self.log("🔢 Xác thực OTP...")
            otp_resp = self.session.post(
                f"{AUTH_BASE}/api/accounts/email-otp/validate",
                json={"code": otp_code},
                headers=reg_headers
            )
            if otp_resp.status_code != 200:
                raise Exception(f"OTP Validation Failed: {otp_resp.text}")

            # Bước 7
            self.log("📋 Hoàn tất tạo Hồ sơ...")
            profile_resp = self.session.post(
                f"{AUTH_BASE}/api/accounts/create_account",
                json={"name": self.name, "birthdate": self.birthdate},
                headers=reg_headers
            )
            
            create_data = profile_resp.json() if profile_resp.text else {}
            continue_url = create_data.get("continue_url") or create_data.get("redirect_url")
            if continue_url:
                self.session.get(continue_url)

            self.log("🎉🎉🎉 ĐĂNG KÝ THÀNH CÔNG! 🎉🎉🎉")
            
            # Lưu tài khoản vào txt
            with open("registered_accounts.txt", "a", encoding="utf-8") as f:
                f.write(f"{self.email}|{self.password}\n")
            self.log("💾 Đã lưu vào registered_accounts.txt")
            return True

        except Exception as e:
            self.log(f"❌ Lỗi đăng ký: {e}")
            return False

if __name__ == "__main__":
    print("="*40)
    print("   ChatGPT Auto Register (Python)   ")
    print("="*40)
    
    pwd = input("Nhập mật khẩu mặc định mong muốn (ví dụ: UsagiAuto123!): ").strip()
    if not pwd:
        pwd = "ChatGPTAuto123!@#"
        
    num = input("Bạn muốn tạo bao nhiêu tài khoản? (Nhấn Enter = 1): ").strip()
    count = int(num) if num.isdigit() else 1
    
    success_count = 0
    for i in range(count):
        print(f"\n--- Đang tạo tài khoản thứ {i+1}/{count} ---")
        creator = ChatGPTAutoReg(password=pwd)
        if creator.register():
            success_count += 1
        time.sleep(2)
        
    print(f"\n✅ Hoàn tất! Đã tạo thành công {success_count}/{count} tài khoản.")
