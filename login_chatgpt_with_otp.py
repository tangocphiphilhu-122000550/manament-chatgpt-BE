"""
Login ChatGPT với OTP - Flow đầy đủ
1. GET /api/auth/providers
2. GET /api/auth/csrf
3. POST /api/auth/signin/openai
4. Lấy OTP từ TempMail
5. POST /api/accounts/email-otp/validate
6. Parse workspace từ cookie oai-client-auth-session
7. Select workspace (nếu có nhiều workspace)
"""

import json
import sys
import uuid
import urllib.parse
import time
import re
import base64
import warnings

# Suppress cookie warnings from curl_cffi
warnings.filterwarnings('ignore', message='.*Multiple cookies.*')

try:
    from curl_cffi import requests
except ImportError:
    print("❌ Chưa cài đặt curl_cffi!")
    print("📦 Chạy: pip install curl_cffi")
    sys.exit(1)

# Config
TEMPMAIL_API_KEY = "tm_2245ae727b49183440bb41338d249dbafd4a5dc193b343b1"
TEMPMAIL_BASE_URL = "https://tempmailapi.io.vn/public_api.php"
TEST_EMAIL = "minhpham97@k20pro.indevs.in"


class ChatGPTLoginWithOTP:
    def __init__(self, email, workspace_id=None):
        self.email = email
        self.workspace_id = workspace_id  # Optional: Cho account có nhiều workspace
        # curl_cffi 0.5.10 chỉ hỗ trợ: chrome99, chrome100, chrome101, chrome104, edge99, edge101, safari15_3, safari15_5
        self.session = requests.Session(impersonate="chrome101")
        
        # Clear any existing cookies to avoid conflicts
        self.session.cookies.clear()
        
        self.device_id = str(uuid.uuid4())
        self.auth_session_id = str(uuid.uuid4())
        self.csrf_token = None
        self.auth_url = None
        self.otp_sent_time = None  # Lưu thời điểm gửi OTP
        self.access_token = None  # Bearer token
        self.user_id = None
        self.account_id = None
        self.account_banned = False  # Flag để detect account bị ban
        
    def log(self, msg):
        print(f"[Login] {msg}")
    
    # ============================================
    # BƯỚC 1: GET Providers
    # ============================================
    def step1_get_providers(self):
        self.log("=" * 70)
        self.log("BƯỚC 1: GET /api/auth/providers")
        self.log("=" * 70)
        
        try:
            response = self.session.get(
                "https://chatgpt.com/api/auth/providers",
                headers={
                    "Accept": "application/json",
                    "Referer": "https://chatgpt.com/"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ Tìm thấy {len(data)} providers")
                return True
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return False
    
    # ============================================
    # BƯỚC 2: GET CSRF Token
    # ============================================
    def step2_get_csrf(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 2: GET /api/auth/csrf")
        self.log("=" * 70)
        
        try:
            response = self.session.get(
                "https://chatgpt.com/api/auth/csrf",
                headers={"Accept": "application/json"}
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.csrf_token = data.get("csrfToken")
                self.log(f"✅ CSRF Token: {self.csrf_token[:30]}...")
                return True
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return False
    
    # ============================================
    # BƯỚC 3: POST Signin
    # ============================================
    def step3_signin(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 3: POST /api/auth/signin/openai")
        self.log("=" * 70)
        
        self.log(f"Email: {self.email}")
        self.log(f"Device ID: {self.device_id}")
        
        try:
            signin_params = {
                'prompt': 'login',
                'ext-oai-did': self.device_id,
                'auth_session_logging_id': self.auth_session_id,
                'ext-passkey-client-capabilities': '1111',
                'screen_hint': 'login_or_signup',
                'login_hint': self.email,
            }
            
            signin_body = {
                'callbackUrl': 'https://chatgpt.com/',
                'csrfToken': self.csrf_token,
                'json': 'true'
            }
            
            signin_url = "https://chatgpt.com/api/auth/signin/openai?" + urllib.parse.urlencode(signin_params)
            
            response = self.session.post(
                signin_url,
                data=signin_body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://chatgpt.com",
                    "Referer": "https://chatgpt.com/",
                    "Accept": "application/json"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.auth_url = data.get('url')
                self.log(f"✅ Auth URL: {self.auth_url[:80]}...")
                
                # Truy cập auth_url - BƯỚC NÀY ĐÃ TỰ ĐỘNG GỬI OTP
                self.log("Đang truy cập auth_url (sẽ tự động gửi OTP)...")
                auth_response = self.session.get(
                    self.auth_url,
                    headers={"Accept": "text/html"}
                )
                self.log(f"Auth URL Status: {auth_response.status_code}")
                
                # LƯU TIMESTAMP NGAY SAU KHI TRUY CẬP AUTH_URL
                self.otp_sent_time = int(time.time())
                self.log(f"✅ OTP đã được gửi tự động! Timestamp: {self.otp_sent_time}")
                
                return True
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                self.log(f"Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return False
    
    # ============================================
    # BƯỚC 3.5: Gửi OTP (KHÔNG CẦN - Auth URL đã tự động gửi)
    # ============================================
    # NOTE: Bước này KHÔNG CẦN THIẾT vì khi truy cập auth_url ở bước 3,
    # OpenAI đã TỰ ĐỘNG gửi OTP rồi. Nếu gọi thêm bước này sẽ gửi 2 lần!
    # Chỉ dùng khi cần RESEND OTP.
    def step3_5_send_otp(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 3.5: GET /api/accounts/email-otp/send (RESEND)")
        self.log("=" * 70)
        
        try:
            send_url = "https://auth.openai.com/api/accounts/email-otp/send"
            
            response = self.session.get(
                send_url,
                headers={
                    "Accept": "text/html,application/json",
                    "Referer": "https://auth.openai.com/"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code in [200, 302]:
                # LƯU THỜI ĐIỂM GỬI OTP (quan trọng!)
                self.otp_sent_time = int(time.time())
                self.log(f"✅ OTP đã được gửi lại! Timestamp: {self.otp_sent_time}")
                return True
            else:
                self.log(f"⚠️  Status: {response.status_code}")
                self.log(f"Response: {response.text[:200]}")
                # Vẫn lưu timestamp vì có thể OTP đã được gửi từ bước signin
                self.otp_sent_time = int(time.time())
                return True
                
        except Exception as e:
            self.log(f"⚠️  Exception: {e}")
            # Vẫn lưu timestamp
            self.otp_sent_time = int(time.time())
            return True
    
    # ============================================
    # BƯỚC 4: Lấy OTP từ TempMail
    # ============================================
    def step4_get_otp(self, max_attempts=24):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 4: Lấy OTP từ TempMail")
        self.log("=" * 70)
        
        self.log(f"Email: {self.email}")
        self.log(f"Đang chờ OTP (tối đa {max_attempts * 5}s)...")
        
        # Sử dụng timestamp từ lúc GỬI OTP (đã lưu ở step 3.5)
        if not self.otp_sent_time:
            self.log("⚠️  Không có otp_sent_time, sử dụng thời gian hiện tại")
            self.otp_sent_time = int(time.time())
        
        self.log(f"⏰ Chỉ lấy email SAU timestamp: {self.otp_sent_time}")
        
        old_emails_count = 0  # Đếm số email cũ để log gọn
        
        for attempt in range(1, max_attempts + 1):
            self.log(f"Lần thử {attempt}/{max_attempts}...")
            
            try:
                list_url = f"{TEMPMAIL_BASE_URL}?action=list&api_key={TEMPMAIL_API_KEY}&email={self.email}&limit=20"
                
                response = self.session.get(list_url, headers={"Accept": "application/json"})
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("success") and data.get("emails"):
                        emails = data.get("emails", [])
                        
                        for mail in emails:
                            subject = mail.get("subject", "")
                            from_addr = mail.get("from", "").lower()
                            mail_timestamp = mail.get("timestamp", 0)
                            mail_date = mail.get("date", "N/A")
                            mail_id = mail.get("id")
                            
                            # CHỈ lấy email MỚI (sau khi GỬI OTP)
                            if mail_timestamp < self.otp_sent_time:
                                old_emails_count += 1
                                continue  # Không log, chỉ đếm
                            
                            # Tìm email từ OpenAI
                            if 'openai' in from_addr or 'chatgpt' in subject.lower():
                                self.log(f"   📧 Email MỚI từ OpenAI: {mail_date}")
                                self.log(f"      Timestamp: {mail_timestamp} (sau khi gửi OTP)")
                                
                                # Thử tìm OTP trong subject trước
                                matches = re.findall(r'\b\d{6}\b', subject)
                                if matches:
                                    for otp in matches:
                                        if otp != '177010':  # Mã test
                                            self.log(f"✅ Tìm thấy OTP trong subject: {otp}")
                                            self.log(f"   From: {mail.get('from', 'N/A')}")
                                            self.log(f"   Subject: {subject}")
                                            self.log(f"   Date: {mail_date}")
                                            return otp
                                
                                # Nếu không có OTP trong subject, đọc body
                                self.log(f"   ⚠️  Không có OTP trong subject, đang đọc body...")
                                
                                try:
                                    read_url = f"{TEMPMAIL_BASE_URL}?action=read&api_key={TEMPMAIL_API_KEY}&email={self.email}&id={mail_id}"
                                    read_response = self.session.get(read_url, headers={"Accept": "application/json"})
                                    
                                    if read_response.status_code == 200:
                                        read_data = read_response.json()
                                        body = read_data.get("body", "")
                                        
                                        # Parse OTP từ body HTML
                                        # Tìm tất cả số 6 chữ số trong body
                                        body_matches = re.findall(r'\b\d{6}\b', body)
                                        
                                        if body_matches:
                                            for otp in body_matches:
                                                if otp != '177010':  # Mã test
                                                    self.log(f"✅ Tìm thấy OTP trong body: {otp}")
                                                    self.log(f"   From: {mail.get('from', 'N/A')}")
                                                    self.log(f"   Subject: {subject}")
                                                    self.log(f"   Date: {mail_date}")
                                                    return otp
                                        else:
                                            self.log(f"   ⚠️  Không tìm thấy OTP trong body")
                                    else:
                                        self.log(f"   ⚠️  Lỗi khi đọc email: {read_response.status_code}")
                                        
                                except Exception as e:
                                    self.log(f"   ⚠️  Lỗi khi đọc body: {e}")
                
            except Exception as e:
                self.log(f"⚠️  Lỗi khi check mail: {e}")
            
            time.sleep(5)
        
        # Log tổng kết
        if old_emails_count > 0:
            self.log(f"💡 Đã bỏ qua {old_emails_count} email cũ")
        
        self.log(f"❌ Không tìm thấy OTP MỚI sau {max_attempts * 5}s")
        self.log(f"💡 Tất cả email đều có timestamp < {self.otp_sent_time}")
        return None
    
    # ============================================
    # Helper: Parse workspace từ cookie
    # ============================================
    def parse_workspace_cookie(self):
        """
        Parse cookie oai-client-auth-session để lấy danh sách workspace
        
        Returns:
            list: Danh sách workspace [{"id": "...", "name": "...", "kind": "..."}]
                  Trả về [] nếu là tài khoản cá nhân (không có workspace)
        """
        try:
            # Lấy cookie oai-client-auth-session
            cookie_value = self.session.cookies.get('oai-client-auth-session')
            
            if not cookie_value:
                self.log("⚠️  Không tìm thấy cookie oai-client-auth-session")
                return []
            
            # Cookie format: base64_data.signature1.signature2
            # Chỉ cần phần base64_data (phần đầu tiên)
            parts = cookie_value.split('.')
            if len(parts) < 1:
                self.log("⚠️  Cookie format không đúng")
                return []
            
            base64_data = parts[0]
            
            # Decode base64
            # Thêm padding nếu cần
            padding = len(base64_data) % 4
            if padding:
                base64_data += '=' * (4 - padding)
            
            decoded = base64.b64decode(base64_data)
            
            # Parse JSON
            data = json.loads(decoded.decode('utf-8'))
            
            # Lấy workspaces
            workspaces = data.get('workspaces', [])
            
            if workspaces:
                self.log(f"✅ Tìm thấy {len(workspaces)} workspace(s):")
                for i, ws in enumerate(workspaces, 1):
                    ws_name = ws.get('name') or '(Personal)'
                    ws_kind = ws.get('kind', 'unknown')
                    self.log(f"   {i}. {ws_name} ({ws_kind})")
                    self.log(f"      ID: {ws.get('id')}")
            else:
                self.log("ℹ️  Không có workspace → Tài khoản cá nhân (Personal/Free)")
            
            return workspaces
            
        except Exception as e:
            self.log(f"⚠️  Lỗi khi parse cookie: {e}")
            return []
    
    # ============================================
    # BƯỚC 5: Validate OTP
    # ============================================
    def step5_validate_otp(self, otp_code):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 5: POST /api/accounts/email-otp/validate")
        self.log("=" * 70)
        
        self.log(f"OTP Code: {otp_code}")
        
        try:
            # Trace headers (giống register_chatgpt.py)
            trace_id = str(uuid.uuid4()).replace('-', '')
            parent_id = format(int(time.time() * 1000000) % (2**64), '016x')
            
            validate_url = "https://auth.openai.com/api/accounts/email-otp/validate"
            
            response = self.session.post(
                validate_url,
                json={"code": otp_code},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://auth.openai.com",
                    "Referer": "https://auth.openai.com/",
                    "Accept": "application/json",
                    "traceparent": f"00-{trace_id}-{parent_id}-01",
                    "tracestate": "dd=s:1;o:rum",
                    "x-datadog-origin": "rum",
                    "x-datadog-sampling-priority": "1"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ OTP hợp lệ!")
                
                try:
                    data = response.json()
                    # Không log response nữa, quá dài
                    
                    # Parse workspace từ cookie
                    self.log("")
                    self.log("=" * 70)
                    self.log("🔍 PARSE WORKSPACE TỪ COOKIE")
                    self.log("=" * 70)
                    workspaces = self.parse_workspace_cookie()
                    
                    # Kiểm tra continue_url
                    continue_url = data.get('continue_url') or data.get('redirect_url')
                    page_type = data.get('page', {}).get('type')
                    
                    if continue_url:
                        self.log(f"\nContinue URL: {continue_url}")
                        self.log(f"Page Type: {page_type}")
                        
                        # Kiểm tra nếu là trang workspace selection
                        if '/workspace' in continue_url or page_type == 'workspace':
                            self.log("\n⚠️  Account thuộc nhiều workspace!")
                            
                            if not workspaces:
                                self.log("❌ Không thể parse workspace từ cookie!")
                                return False
                            
                            if self.workspace_id:
                                # Có workspace_id → Select workspace
                                self.log(f"\n✅ Sử dụng workspace_id: {self.workspace_id}")
                                return self.step5_5_select_workspace(self.workspace_id, continue_url)
                            else:
                                # Không có workspace_id → Tự động chọn workspace đầu tiên
                                self.log("\n⚠️  Không có workspace_id, tự động chọn workspace đầu tiên")
                                first_workspace_id = workspaces[0]['id']
                                first_workspace_name = workspaces[0].get('name') or '(Personal)'
                                self.log(f"   → Chọn: {first_workspace_name}")
                                self.log(f"   → ID: {first_workspace_id}")
                                return self.step5_5_select_workspace(first_workspace_id, continue_url)
                        else:
                            # Truy cập continue_url để hoàn tất flow
                            self.log("\n✅ Account chỉ có 1 workspace, đang hoàn tất login...")
                            final_response = self.session.get(
                                continue_url,
                                headers={"Accept": "text/html"},
                                allow_redirects=True
                            )
                            self.log(f"Final Status: {final_response.status_code}")
                            self.log(f"Final URL: {final_response.url}")
                            
                            # Nếu redirect về ChatGPT, follow redirect
                            if "chatgpt.com" in final_response.url:
                                self.log("✅ Đã redirect về ChatGPT!")
                        
                except:
                    self.log("Response không phải JSON")
                
                return True
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                
                # Check if account is banned/deactivated
                try:
                    error_data = response.json()
                    if error_data.get('error', {}).get('code') == 'account_deactivated':
                        self.log("🚫 ACCOUNT BỊ BAN/DEACTIVATED!")
                        self.log(f"Message: {error_data.get('error', {}).get('message')}")
                        self.account_banned = True
                        return 'banned'
                except:
                    pass
                
                self.log(f"Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ============================================
    # BƯỚC 5.5: Select Workspace (Nếu có nhiều workspace)
    # ============================================
    def step5_5_select_workspace(self, workspace_id, workspace_url):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 5.5: POST /api/accounts/workspace/select")
        self.log("=" * 70)
        
        self.log(f"Workspace ID: {workspace_id}")
        
        try:
            response = self.session.post(
                "https://auth.openai.com/api/accounts/workspace/select",
                json={"workspace_id": workspace_id},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://auth.openai.com",
                    "Referer": workspace_url,
                    "Accept": "application/json"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ Đã chọn workspace!")
                
                try:
                    data = response.json()
                    self.log("Response:")
                    self.log(json.dumps(data, indent=2))
                    
                    # Lấy continue_url
                    continue_url = data.get('continue_url')
                    
                    if continue_url:
                        self.log(f"Continue URL: {continue_url}")
                        
                        # Truy cập continue_url
                        self.log("Đang truy cập continue_url...")
                        final_response = self.session.get(
                            continue_url,
                            headers={"Accept": "text/html"},
                            allow_redirects=True
                        )
                        self.log(f"Final Status: {final_response.status_code}")
                        self.log(f"Final URL: {final_response.url}")
                        
                        if "chatgpt.com" in final_response.url:
                            self.log("✅ Đã redirect về ChatGPT!")
                
                except:
                    self.log("Response không phải JSON")
                
                return True
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                self.log(f"Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ============================================
    # BƯỚC 6: Lấy Session & Access Token
    # ============================================
    def step6_get_session(self, max_retries=5):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 6: GET /api/auth/session")
        self.log("=" * 70)
        
        # Đợi một chút để session được cập nhật
        self.log("⏳ Đợi 2s để session được cập nhật...")
        time.sleep(2)
        
        for attempt in range(1, max_retries + 1):
            try:
                self.log(f"Lần thử {attempt}/{max_retries}...")
                
                response = self.session.get(
                    "https://chatgpt.com/api/auth/session",
                    headers={"Accept": "application/json"}
                )
                
                self.log(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Kiểm tra xem có user data không
                    if "user" not in data or not data.get("user"):
                        self.log("⚠️  Session chưa có user data, thử lại...")
                        
                        if attempt < max_retries:
                            time.sleep(2)
                            continue
                        else:
                            self.log("❌ Session vẫn chưa có user data sau nhiều lần thử")
                            self.log(f"Response: {json.dumps(data, indent=2)}")
                            return False
                    
                    # Lấy access token
                    self.access_token = data.get("accessToken")
                    self.user_id = data.get("user", {}).get("id")
                    
                    account_data = data.get("account")
                    if account_data:
                        self.account_id = account_data.get("id")
                    
                    self.log(f"✅ User ID: {self.user_id}")
                    self.log(f"✅ Account ID: {self.account_id}")
                    
                    if self.access_token:
                        self.log(f"✅ Access Token: {self.access_token[:50]}...")
                    else:
                        self.log("⚠️  Không có Access Token")
                    
                    return True
                else:
                    self.log(f"❌ Lỗi: {response.status_code}")
                    
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    
                    return False
                    
            except Exception as e:
                self.log(f"❌ Exception: {e}")
                
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                
                import traceback
                traceback.print_exc()
                return False
        
        return False
    
    # ============================================
    # BƯỚC 7: Lấy thông tin User (/me)
    # ============================================
    def step7_get_me(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 7: GET /backend-api/me")
        self.log("=" * 70)
        
        try:
            response = self.session.get(
                "https://chatgpt.com/backend-api/me",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                self.log(f"✅ Email: {data.get('email')}")
                self.log(f"✅ Name: {data.get('name')}")
                self.log(f"✅ Created: {data.get('created')}")
                self.log(f"✅ MFA Enabled: {data.get('mfa_flag_enabled')}")
                
                # Lấy organization info
                orgs = data.get("orgs", {}).get("data", [])
                if orgs:
                    org = orgs[0]
                    self.log(f"✅ Organization: {org.get('title')} ({org.get('role')})")
                
                return data
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return None
    
    # ============================================
    # BƯỚC 8: Lấy thông tin Subscription
    # ============================================
    def step8_get_subscription(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 8: GET /backend-api/subscriptions")
        self.log("=" * 70)
        
        if not self.account_id:
            self.log("❌ Không có account_id")
            return None
        
        try:
            response = self.session.get(
                f"https://chatgpt.com/backend-api/subscriptions?account_id={self.account_id}",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                self.log(f"✅ Plan Type: {data.get('plan_type')}")
                self.log(f"✅ Seats In Use: {data.get('seats_in_use')}/{data.get('seats_entitled')}")
                self.log(f"✅ Active Until: {data.get('active_until')}")
                self.log(f"✅ Will Renew: {data.get('will_renew')}")
                
                return data
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return None
    
    # ============================================
    # BƯỚC 9: Lấy danh sách Users trong Workspace
    # ============================================
    def step9_get_workspace_users(self):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 9: GET /backend-api/accounts/{account_id}/users")
        self.log("=" * 70)
        
        if not self.account_id:
            self.log("❌ Không có account_id")
            return None
        
        try:
            response = self.session.get(
                f"https://chatgpt.com/backend-api/accounts/{self.account_id}/users?offset=0&limit=25&query=",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                users = data.get("items", [])
                self.log(f"✅ Tổng số users: {data.get('total')}")
                
                for i, user in enumerate(users, 1):
                    self.log(f"   {i}. {user.get('name')} ({user.get('email')})")
                    self.log(f"      Role: {user.get('role')}")
                    self.log(f"      Seat Type: {user.get('seat_type')}")
                
                return data
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                return None
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return None
    
    # ============================================
    # BƯỚC 10: Mời User mới vào Workspace
    # ============================================
    def step10_invite_user(self, email_address, role="standard-user", seat_type="default"):
        self.log("")
        self.log("=" * 70)
        self.log("BƯỚC 10: POST /backend-api/accounts/{account_id}/invites")
        self.log("=" * 70)
        
        if not self.account_id:
            self.log("❌ Không có account_id")
            return None
        
        self.log(f"Email: {email_address}")
        self.log(f"Role: {role}")
        self.log(f"Seat Type: {seat_type}")
        
        try:
            response = self.session.post(
                f"https://chatgpt.com/backend-api/accounts/{self.account_id}/invites",
                json={
                    "email_addresses": [email_address],
                    "role": role,
                    "seat_type": seat_type,
                    "resend_emails": True
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                }
            )
            
            self.log(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                invites = data.get("account_invites", [])
                errors = data.get("errored_emails", [])
                
                if invites:
                    self.log(f"✅ Đã gửi lời mời thành công!")
                    for invite in invites:
                        self.log(f"   Email: {invite.get('email_address')}")
                        self.log(f"   Invite ID: {invite.get('id')}")
                        self.log(f"   Created: {invite.get('created_time')}")
                
                if errors:
                    self.log(f"❌ Lỗi với các email:")
                    for error in errors:
                        self.log(f"   {error}")
                
                return data
            else:
                self.log(f"❌ Lỗi: {response.status_code}")
                self.log(f"Response: {response.text[:200]}")
                return None
                
        except Exception as e:
            self.log(f"❌ Exception: {e}")
            return None
    
    # ============================================
    # Main Flow
    # ============================================
    def login(self):
        self.log("\n")
        self.log("=" * 70)
        self.log("  ChatGPT Login với OTP - Full Flow")
        self.log("=" * 70)
        self.log("")
        
        # Bước 1: Providers
        if not self.step1_get_providers():
            self.log("\n❌ Thất bại ở bước 1")
            return False
        
        # Bước 2: CSRF
        if not self.step2_get_csrf():
            self.log("\n❌ Thất bại ở bước 2")
            return False
        
        # Bước 3: Signin (tự động gửi OTP)
        if not self.step3_signin():
            self.log("\n❌ Thất bại ở bước 3")
            return False
        
        # Bước 4: Get OTP
        otp_code = self.step4_get_otp()
        if not otp_code:
            self.log("\n❌ Thất bại ở bước 4")
            return False
        
        # Bước 5: Validate OTP
        if not self.step5_validate_otp(otp_code):
            self.log("\n❌ Thất bại ở bước 5")
            return False
        
        # Bước 6: Get Session & Access Token
        if not self.step6_get_session():
            self.log("\n❌ Thất bại ở bước 6")
            return False
        
        # Bước 7: Get User Info
        self.step7_get_me()
        
        # Bước 8: Get Subscription Info
        self.step8_get_subscription()
        
        # Bước 9: Get Workspace Users
        self.step9_get_workspace_users()
        
        # Thành công
        self.log("")
        self.log("=" * 70)
        self.log("  🎉 ĐĂNG NHẬP THÀNH CÔNG!")
        self.log("=" * 70)
        self.log("")
        
        return True


def main():
    print("\n")
    print("=" * 70)
    print("  ChatGPT Login với OTP")
    print("=" * 70)
    print("\n")
    
    print(f"📧 Email: {TEST_EMAIL}")
    print(f"🔑 TempMail API Key: {TEMPMAIL_API_KEY[:20]}...")
    print()
    
    # Khởi tạo và login
    login_bot = ChatGPTLoginWithOTP(email=TEST_EMAIL)
    success = login_bot.login()
    
    if success:
        print("\n✅ Hoàn tất!")
        print("💡 Session đã được authenticate")
        print(f"💡 Access Token: {login_bot.access_token[:50]}...")
        print(f"💡 User ID: {login_bot.user_id}")
        print(f"💡 Account ID: {login_bot.account_id}")
        print()
        
        # Demo: Mời user mới (nếu muốn test)
        # invite_email = input("Nhập email để mời vào workspace (Enter để bỏ qua): ").strip()
        # if invite_email:
        #     login_bot.step10_invite_user(invite_email)
    else:
        print("\n❌ Login thất bại!")
        print("💡 Kiểm tra lại email hoặc TempMail API")


if __name__ == "__main__":
    main()
