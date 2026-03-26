"""
Flask Web App - ChatGPT Account Manager
"""

import os
import json
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from bson import ObjectId

from database import db

# Test MongoDB connection
try:
    db.client.admin.command('ping')
    print("✅ MongoDB connected successfully")
except Exception as e:
    print(f"⚠️  MongoDB connection failed: {e}")
    print("⚠️  App will start but database operations will fail")
from login_chatgpt_with_otp import ChatGPTLoginWithOTP

# Import Google Sheet Manager
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False
    print("⚠️  Google Sheets API not available. Install: pip install google-auth google-api-python-client")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
CORS(app)

# Custom JSON encoder để xử lý ObjectId và datetime
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = JSONEncoder

# Helper function to convert MongoDB documents to JSON-safe format
def mongo_to_dict(doc):
    """Convert MongoDB document to JSON-safe dict"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [mongo_to_dict(item) for item in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = mongo_to_dict(value)
            elif isinstance(value, list):
                result[key] = mongo_to_dict(value)
            else:
                result[key] = value
        return result
    return doc


# ============================================
# ROUTES - Health Check
# ============================================

@app.route('/health', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for monitoring services"""
    if request.method == 'HEAD':
        return '', 200
    
    return jsonify({
        'status': 'healthy',
        'service': 'chatgpt-account-manager',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/')
def index():
    """API root endpoint"""
    # Check MongoDB status
    mongodb_status = "connected" if db.client else "disconnected"
    mongodb_error = None
    
    if not db.client:
        mongodb_error = "MongoDB connection failed - check MONGODB_URI environment variable"
    
    return jsonify({
        'service': 'ChatGPT Account Manager API',
        'version': '1.0.0',
        'status': 'running',
        'mongodb': {
            'status': mongodb_status,
            'error': mongodb_error
        },
        'environment': {
            'MONGODB_URI_set': bool(os.getenv('MONGODB_URI')),
            'MONGODB_DB': os.getenv('MONGODB_DB', 'not set')
        },
        'endpoints': {
            'health': '/health',
            'statistics': '/api/statistics',
            'accounts': '/api/accounts',
            'login': '/api/login',
            'logs': '/api/logs'
        }
    }), 200


# ============================================
# API - Statistics
# ============================================

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Lấy thống kê tổng quan"""
    try:
        stats = db.get_statistics()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        import traceback
        error_detail = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"❌ Statistics API Error: {error_detail}")
        return jsonify({'success': False, 'error': str(e), 'detail': error_detail}), 500


# ============================================
# API - Accounts
# ============================================

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Lấy danh sách accounts"""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        skip = int(request.args.get('skip', 0))
        
        accounts = db.get_all_accounts(status, limit, skip)
        total = db.count_accounts(status)
        
        # Convert MongoDB documents to JSON-safe format
        accounts_json = mongo_to_dict(accounts)
        
        return jsonify({
            'success': True,
            'data': accounts_json,
            'total': total,
            'limit': limit,
            'skip': skip
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>', methods=['GET'])
def get_account(account_id):
    """Lấy thông tin account"""
    try:
        account = db.get_account_by_id(account_id)
        
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Lấy session
        session_data = db.get_session(account_id)
        
        return jsonify({
            'success': True,
            'data': {
                'account': mongo_to_dict(account),
                'session': mongo_to_dict(session_data)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts', methods=['POST'])
def create_account():
    """Tạo account mới"""
    try:
        data = request.json
        
        email = data.get('email')
        password = data.get('password', '171004Minh@@')
        account_type = data.get('account_type', 'Team')
        source = data.get('source', 'mailp.tech')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Kiểm tra email đã tồn tại
        existing = db.get_account_by_email(email)
        if existing:
            return jsonify({'success': False, 'error': 'Email already exists'}), 400
        
        # Tạo account
        account = db.create_account(email, password, account_type, source)
        
        if account:
            return jsonify({'success': True, 'data': mongo_to_dict(account)}), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to create account'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>', methods=['PUT'])
def update_account(account_id):
    """Cập nhật account"""
    try:
        data = request.json
        
        # Không cho phép update email
        if 'email' in data:
            del data['email']
        
        # Không cho phép update _id
        if '_id' in data:
            del data['_id']
        
        success = db.update_account(account_id, data)
        
        if success:
            account = db.get_account_by_id(account_id)
            return jsonify({'success': True, 'data': mongo_to_dict(account)})
        else:
            return jsonify({'success': False, 'error': 'Failed to update account'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Xóa account"""
    try:
        success = db.delete_account(account_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Account deleted'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete account'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/refresh-users', methods=['POST'])
def refresh_account_users(account_id):
    """Refresh số lượng users trong workspace"""
    try:
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Lấy session
        session_data = db.get_session(account_id)
        if not session_data:
            return jsonify({'success': False, 'error': 'No active session found'}), 404
        
        # Khởi tạo login bot với session hiện tại
        email = account['email']
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Restore session data
        login_bot.access_token = session_data['session_data'].get('access_token')
        login_bot.user_id = session_data['session_data'].get('user_id')
        login_bot.account_id = session_data['session_data'].get('account_id')
        
        # Restore cookies
        cookies = session_data.get('cookies', {})
        for cookie_key, cookie_value in cookies.items():
            # Parse cookie_key format: "name@domain"
            if '@' in cookie_key:
                name, domain = cookie_key.split('@', 1)
                login_bot.session.cookies.set(name, cookie_value, domain=domain)
            else:
                login_bot.session.cookies.set(cookie_key, cookie_value)
        
        # Gọi API lấy users
        users_data = login_bot.step9_get_workspace_users()
        
        if not users_data:
            return jsonify({'success': False, 'error': 'Failed to get workspace users'}), 500
        
        total_users = users_data.get('total', 0)
        
        # Cập nhật vào DB
        db.update_account(account_id, {'total_users': total_users})
        db.add_log(account_id, 'users_refreshed', f'Refreshed users count: {total_users}')
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'users': users_data.get('items', [])
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/invite-user', methods=['POST'])
def invite_user_to_team(account_id):
    """Mời user vào team workspace"""
    try:
        data = request.json
        email_address = data.get('email')
        role = data.get('role', 'standard-user')
        seat_type = data.get('seat_type', 'default')
        
        if not email_address:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Kiểm tra account type
        if account.get('account_type') != 'Team':
            return jsonify({'success': False, 'error': 'Only Team accounts can invite users'}), 400
        
        # Lấy session
        session_data = db.get_session(account_id)
        if not session_data:
            return jsonify({'success': False, 'error': 'No active session found'}), 404
        
        # Khởi tạo login bot với session hiện tại
        email = account['email']
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Restore session data
        login_bot.access_token = session_data['session_data'].get('access_token')
        login_bot.user_id = session_data['session_data'].get('user_id')
        login_bot.account_id = session_data['session_data'].get('account_id')
        
        # Restore cookies
        cookies = session_data.get('cookies', {})
        for cookie_key, cookie_value in cookies.items():
            if '@' in cookie_key:
                name, domain = cookie_key.split('@', 1)
                login_bot.session.cookies.set(name, cookie_value, domain=domain)
            else:
                login_bot.session.cookies.set(cookie_key, cookie_value)
        
        # Gọi API mời user
        try:
            invite_response = login_bot.session.post(
                f"https://chatgpt.com/backend-api/accounts/{login_bot.account_id}/invites",
                json={
                    "email_addresses": [email_address],
                    "role": role,
                    "seat_type": seat_type,
                    "resend_emails": True
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {login_bot.access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if invite_response.status_code == 200:
                result = invite_response.json()
                
                account_invites = result.get('account_invites', [])
                errored_emails = result.get('errored_emails', [])
                
                if errored_emails:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to invite: {errored_emails}'
                    }), 400
                
                # Log
                db.add_log(account_id, 'user_invited', f'Invited {email_address} to team')
                
                # Refresh user count
                users_data = login_bot.step9_get_workspace_users()
                if users_data:
                    total_users = users_data.get('total', 0)
                    db.update_account(account_id, {'total_users': total_users})
                
                return jsonify({
                    'success': True,
                    'data': {
                        'invites': account_invites,
                        'total_users': total_users if users_data else None
                    }
                })
            else:
                error_msg = invite_response.text
                return jsonify({'success': False, 'error': f'API error: {error_msg}'}), invite_response.status_code
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/invites', methods=['GET'])
def get_pending_invites(account_id):
    """Lấy danh sách lời mời đang pending"""
    try:
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Lấy session
        session_data = db.get_session(account_id)
        if not session_data:
            return jsonify({'success': False, 'error': 'No active session found'}), 404
        
        # Khởi tạo login bot với session hiện tại
        email = account['email']
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Restore session data
        login_bot.access_token = session_data['session_data'].get('access_token')
        login_bot.user_id = session_data['session_data'].get('user_id')
        login_bot.account_id = session_data['session_data'].get('account_id')
        
        # Restore cookies
        cookies = session_data.get('cookies', {})
        for cookie_key, cookie_value in cookies.items():
            if '@' in cookie_key:
                name, domain = cookie_key.split('@', 1)
                login_bot.session.cookies.set(name, cookie_value, domain=domain)
            else:
                login_bot.session.cookies.set(cookie_key, cookie_value)
        
        # Gọi API lấy invites
        try:
            invites_response = login_bot.session.get(
                f"https://chatgpt.com/backend-api/accounts/{login_bot.account_id}/invites?offset=0&limit=25&query=",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {login_bot.access_token}"
                }
            )
            
            if invites_response.status_code == 200:
                result = invites_response.json()
                
                return jsonify({
                    'success': True,
                    'data': {
                        'invites': result.get('items', []),
                        'total': result.get('total', 0)
                    }
                })
            else:
                error_msg = invites_response.text
                return jsonify({'success': False, 'error': f'API error: {error_msg}'}), invites_response.status_code
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/invites/<email>', methods=['DELETE'])
def delete_invite(account_id, email):
    """Xóa lời mời"""
    try:
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        # Lấy session
        session_data = db.get_session(account_id)
        if not session_data:
            return jsonify({'success': False, 'error': 'No active session found'}), 404
        
        # Khởi tạo login bot với session hiện tại
        account_email = account['email']
        login_bot = ChatGPTLoginWithOTP(email=account_email)
        
        # Restore session data
        login_bot.access_token = session_data['session_data'].get('access_token')
        login_bot.user_id = session_data['session_data'].get('user_id')
        login_bot.account_id = session_data['session_data'].get('account_id')
        
        # Restore cookies
        cookies = session_data.get('cookies', {})
        for cookie_key, cookie_value in cookies.items():
            if '@' in cookie_key:
                name, domain = cookie_key.split('@', 1)
                login_bot.session.cookies.set(name, cookie_value, domain=domain)
            else:
                login_bot.session.cookies.set(cookie_key, cookie_value)
        
        # Gọi API xóa invite
        try:
            delete_response = login_bot.session.delete(
                f"https://chatgpt.com/backend-api/accounts/{login_bot.account_id}/invites",
                json={"email_address": email},
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {login_bot.access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if delete_response.status_code == 200:
                result = delete_response.json()
                
                # Log
                db.add_log(account_id, 'invite_deleted', f'Deleted invite for {email}')
                
                return jsonify({
                    'success': True,
                    'data': result
                })
            else:
                error_msg = delete_response.text
                return jsonify({'success': False, 'error': f'API error: {error_msg}'}), delete_response.status_code
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API - Login Account
# ============================================

@app.route('/api/login', methods=['POST'])
def login_account():
    """Login account với OTP"""
    try:
        data = request.json
        
        email = data.get('email')
        password = data.get('password', '171004Minh@@')
        account_type = data.get('account_type', 'Team')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Tạo hoặc lấy account
        account = db.get_account_by_email(email)
        if not account:
            account = db.create_account(email, password, account_type)
            if not account:
                return jsonify({'success': False, 'error': 'Failed to create account'}), 500
        
        account_id = str(account['_id'])
        
        # Khởi tạo login bot
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Step 1-3: Gửi OTP
        db.add_log(account_id, 'login_started', f'Starting login for {email}')
        
        if not login_bot.step1_get_providers():
            return jsonify({'success': False, 'error': 'Failed to get providers'}), 500
        
        if not login_bot.step2_get_csrf():
            return jsonify({'success': False, 'error': 'Failed to get CSRF token'}), 500
        
        if not login_bot.step3_signin():
            return jsonify({'success': False, 'error': 'Failed to signin'}), 500
        
        db.add_log(account_id, 'otp_sent', 'OTP sent to email')
        
        return jsonify({
            'success': True,
            'message': 'OTP sent',
            'account_id': account_id,
            'email': email
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/login/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP và hoàn tất login"""
    try:
        data = request.json
        
        account_id = data.get('account_id')
        otp_code = data.get('otp_code')
        
        if not account_id or not otp_code:
            return jsonify({'success': False, 'error': 'account_id and otp_code are required'}), 400
        
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        email = account['email']
        
        # Khởi tạo login bot
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Restore session từ previous steps (cần implement session storage)
        # Tạm thời chạy lại từ đầu
        login_bot.step1_get_providers()
        login_bot.step2_get_csrf()
        login_bot.step3_signin()
        
        # Validate OTP
        validate_result = login_bot.step5_validate_otp(otp_code)
        
        if validate_result == 'banned':
            db.add_log(account_id, 'login_failed', 'Account is banned/deactivated', 'error')
            db.update_account_status(account_id, 'banned')
            
            # Update Google Sheet cột G
            account = db.get_account_by_id(account_id)
            if account:
                update_google_sheet_status(account['email'], ban_status='banned')
            
            return jsonify({'success': False, 'error': 'Account is banned or deactivated'}), 403
        
        if not validate_result:
            db.add_log(account_id, 'login_failed', 'OTP validation failed', 'error')
            return jsonify({'success': False, 'error': 'Invalid OTP'}), 400
        
        db.add_log(account_id, 'otp_validated', 'OTP validated successfully')
        
        # Lấy session data
        login_bot.step6_get_session()
        
        # Lưu session vào database
        session_data = {
            'access_token': login_bot.access_token,
            'user_id': login_bot.user_id,
            'account_id': login_bot.account_id
        }
        
        cookies = dict(login_bot.session.cookies)
        
        db.save_session(account_id, session_data, cookies)
        
        # Update account status
        db.update_account_status(account_id, 'active')
        
        # Lấy thông tin user
        me_data = login_bot.step7_get_me()
        if me_data:
            db.update_account(account_id, {
                'user_id': me_data.get('id'),
                'name': me_data.get('name'),
                'email_verified': me_data.get('email_verified')
            })
        
        # Lấy subscription
        sub_data = login_bot.step8_get_subscription()
        if sub_data:
            db.update_account_subscription(account_id, sub_data)
            
            # Detect account_type: chỉ có 2 loại - Personal hoặc Team
            plan_type = sub_data.get('plan_type', '').lower()
            if 'team' in plan_type or 'business' in plan_type or 'enterprise' in plan_type:
                db.update_account(account_id, {'account_type': 'Team'})
            else:
                # Plus, Free, hoặc bất kỳ loại nào khác → Personal
                db.update_account(account_id, {'account_type': 'Personal'})
        
        # Step 9: Lấy số lượng users trong workspace
        users_data = login_bot.step9_get_workspace_users()
        if users_data:
            total_users = users_data.get('total', 0)
            db.update_account(account_id, {'total_users': total_users})
        else:
            # Nếu không lấy được users (có thể là tài khoản Personal), set total_users = 1
            db.update_account(account_id, {'total_users': 1})
        
        db.add_log(account_id, 'login_success', 'Login completed successfully')
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'data': {
                'account_id': account_id,
                'email': email,
                'session': session_data
            }
        })
        
    except Exception as e:
        db.add_log(account_id, 'login_error', str(e), 'error')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/login/auto-otp', methods=['POST'])
def auto_login_with_otp():
    """Tự động lấy OTP từ TempMail và login"""
    try:
        data = request.json
        
        email = data.get('email')
        password = data.get('password', '171004Minh@@')
        account_type = data.get('account_type', 'Team')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        # Tạo hoặc lấy account
        account = db.get_account_by_email(email)
        if not account:
            account = db.create_account(email, password, account_type)
            if not account:
                return jsonify({'success': False, 'error': 'Failed to create account'}), 500
        
        account_id = str(account['_id'])
        
        # Khởi tạo login bot
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Full flow
        db.add_log(account_id, 'auto_login_started', f'Starting auto login for {email}')
        
        # Step 1-3: Gửi OTP
        login_bot.step1_get_providers()
        login_bot.step2_get_csrf()
        login_bot.step3_signin()
        
        db.add_log(account_id, 'otp_sent', 'OTP sent, waiting for email...')
        
        # Step 4: Tự động lấy OTP
        otp_code = login_bot.step4_get_otp(max_attempts=24)
        
        if not otp_code:
            db.add_log(account_id, 'auto_login_failed', 'Failed to get OTP from email', 'error')
            return jsonify({'success': False, 'error': 'Failed to get OTP from email'}), 500
        
        db.add_log(account_id, 'otp_received', f'OTP received: {otp_code}')
        
        # Step 5: Validate OTP
        validate_result = login_bot.step5_validate_otp(otp_code)
        
        if validate_result == 'banned':
            db.add_log(account_id, 'auto_login_failed', 'Account is banned/deactivated', 'error')
            db.update_account_status(account_id, 'banned')
            
            # Update Google Sheet cột G
            account = db.get_account_by_id(account_id)
            if account:
                update_google_sheet_status(account['email'], ban_status='banned')
            
            return jsonify({'success': False, 'error': 'Account is banned or deactivated'}), 403
        
        if not validate_result:
            db.add_log(account_id, 'auto_login_failed', 'OTP validation failed', 'error')
            return jsonify({'success': False, 'error': 'Invalid OTP'}), 400
        
        # Step 6-8: Lấy thông tin
        login_bot.step6_get_session()
        
        # Lưu session
        session_data = {
            'access_token': login_bot.access_token,
            'user_id': login_bot.user_id,
            'account_id': login_bot.account_id
        }
        
        cookies = dict(login_bot.session.cookies)
        db.save_session(account_id, session_data, cookies)
        
        # Update account
        db.update_account_status(account_id, 'active')
        
        me_data = login_bot.step7_get_me()
        if me_data:
            db.update_account(account_id, {
                'user_id': me_data.get('id'),
                'name': me_data.get('name'),
                'email_verified': me_data.get('email_verified')
            })
        
        sub_data = login_bot.step8_get_subscription()
        if sub_data:
            db.update_account_subscription(account_id, sub_data)
            
            # Detect account_type: chỉ có 2 loại - Personal hoặc Team
            plan_type = sub_data.get('plan_type', '').lower()
            if 'team' in plan_type or 'business' in plan_type or 'enterprise' in plan_type:
                db.update_account(account_id, {'account_type': 'Team'})
            else:
                # Plus, Free, hoặc bất kỳ loại nào khác → Personal
                db.update_account(account_id, {'account_type': 'Personal'})
        
        # Step 9: Lấy số lượng users trong workspace
        users_data = login_bot.step9_get_workspace_users()
        if users_data:
            total_users = users_data.get('total', 0)
            db.update_account(account_id, {'total_users': total_users})
        else:
            # Nếu không lấy được users (có thể là tài khoản Personal), set total_users = 1
            db.update_account(account_id, {'total_users': 1})
        
        db.add_log(account_id, 'auto_login_success', 'Auto login completed successfully')
        
        return jsonify({
            'success': True,
            'message': 'Auto login successful',
            'data': {
                'account_id': account_id,
                'email': email,
                'otp_code': otp_code,
                'session': session_data
            }
        })
        
    except Exception as e:
        if 'account_id' in locals():
            db.add_log(account_id, 'auto_login_error', str(e), 'error')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API - Sessions
# ============================================

@app.route('/api/sessions/<account_id>', methods=['GET'])
def get_session(account_id):
    """Lấy session của account"""
    try:
        session_data = db.get_session(account_id)
        
        if not session_data:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        return jsonify({'success': True, 'data': mongo_to_dict(session_data)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sessions/<account_id>', methods=['DELETE'])
def invalidate_session(account_id):
    """Vô hiệu hóa session"""
    try:
        success = db.invalidate_session(account_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Session invalidated'})
        else:
            return jsonify({'success': False, 'error': 'Failed to invalidate session'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API - Logs
# ============================================

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Lấy logs"""
    try:
        account_id = request.args.get('account_id')
        limit = int(request.args.get('limit', 100))
        
        logs = db.get_logs(account_id, limit)
        
        return jsonify({'success': True, 'data': mongo_to_dict(logs)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# API - Google Sheet Integration
# ============================================

@app.route('/api/accounts/<account_id>/check-ban', methods=['POST'])
def check_account_ban(account_id):
    """Kiểm tra account có bị ban không bằng cách login đến bước validate OTP"""
    try:
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        email = account['email']
        
        db.add_log(account_id, 'check_ban_started', f'Starting ban check for {email}')
        
        # Khởi tạo login bot
        login_bot = ChatGPTLoginWithOTP(email=email)
        
        # Step 1-3: Gửi OTP
        if not login_bot.step1_get_providers():
            return jsonify({'success': False, 'error': 'Failed to get providers'}), 500
        
        if not login_bot.step2_get_csrf():
            return jsonify({'success': False, 'error': 'Failed to get CSRF token'}), 500
        
        if not login_bot.step3_signin():
            return jsonify({'success': False, 'error': 'Failed to signin'}), 500
        
        db.add_log(account_id, 'check_ban_otp_sent', 'OTP sent, waiting for email...')
        
        # Step 4: Tự động lấy OTP
        otp_code = login_bot.step4_get_otp(max_attempts=24)
        
        if not otp_code:
            db.add_log(account_id, 'check_ban_failed', 'Failed to get OTP from email', 'error')
            return jsonify({'success': False, 'error': 'Failed to get OTP from email'}), 500
        
        db.add_log(account_id, 'check_ban_otp_received', f'OTP received: {otp_code}')
        
        # Step 5: Validate OTP (đây là bước kiểm tra ban)
        validate_result = login_bot.step5_validate_otp(otp_code)
        
        if validate_result == 'banned':
            db.add_log(account_id, 'check_ban_detected', 'Account is BANNED/DEACTIVATED', 'error')
            db.update_account_status(account_id, 'banned')
            
            # Update Google Sheet cột G
            update_google_sheet_status(email, ban_status='banned')
            
            return jsonify({
                'success': True,
                'data': {
                    'is_banned': True,
                    'status': 'banned',
                    'message': 'Account is banned or deactivated'
                }
            })
        
        if not validate_result:
            db.add_log(account_id, 'check_ban_failed', 'OTP validation failed', 'error')
            return jsonify({'success': False, 'error': 'Invalid OTP'}), 400
        
        # OTP hợp lệ → Account không bị ban
        db.add_log(account_id, 'check_ban_completed', 'Account is NOT banned')
        
        # Nếu account đang ở trạng thái banned nhưng check thấy OK → update lại
        if account.get('status') == 'banned':
            db.update_account_status(account_id, 'active')
            update_google_sheet_status(email, ban_status='active')
        
        return jsonify({
            'success': True,
            'data': {
                'is_banned': False,
                'status': 'active',
                'message': 'Account is active and not banned'
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        if 'account_id' in locals():
            db.add_log(account_id, 'check_ban_error', str(e), 'error')
        
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accounts/<account_id>/sale-status', methods=['PUT'])
def update_sale_status(account_id):
    """Cập nhật trạng thái bán của account và sync với Google Sheet"""
    try:
        data = request.json
        sale_status = data.get('sale_status')  # 'sold' hoặc 'available'
        
        if sale_status not in ['sold', 'available']:
            return jsonify({'success': False, 'error': 'Invalid sale_status'}), 400
        
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        email = account['email']
        
        # Update DB
        db.update_account(account_id, {'sale_status': sale_status})
        db.add_log(account_id, 'sale_status_updated', f'Sale status changed to {sale_status}')
        
        # Update Google Sheet cột F
        update_google_sheet_status(email, sale_status=sale_status)
        
        return jsonify({
            'success': True,
            'data': {
                'sale_status': sale_status
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def update_google_sheet_status(email, sale_status=None, ban_status=None):
    """Helper function để update Google Sheet cột F (sale) và G (ban)"""
    if not GOOGLE_SHEETS_AVAILABLE:
        return
    
    try:
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account.json')
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Bảng_1')
        
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        
        # Tìm row của email trong sheet
        range_name = f'{sheet_name}!A2:A1000'
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        row_number = None
        
        for i, row in enumerate(values, start=2):
            if row and len(row) > 0 and row[0].strip() == email:
                row_number = i
                break
        
        if not row_number:
            print(f"⚠️  Email {email} not found in Google Sheet")
            return
        
        # Update cột F (sale status) nếu có
        if sale_status:
            sale_text = 'Đã Bán' if sale_status == 'sold' else 'Chưa Bán'
            update_range = f'{sheet_name}!F{row_number}'
            
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=update_range,
                valueInputOption='RAW',
                body={'values': [[sale_text]]}
            ).execute()
            
            print(f"✅ Updated Google Sheet F{row_number} = {sale_text}")
        
        # Update cột G (ban status) nếu có
        if ban_status:
            ban_text = 'Ban' if ban_status == 'banned' else 'No ban'
            update_range = f'{sheet_name}!G{row_number}'
            
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=update_range,
                valueInputOption='RAW',
                body={'values': [[ban_text]]}
            ).execute()
            
            print(f"✅ Updated Google Sheet G{row_number} = {ban_text}")
            
    except Exception as e:
        print(f"⚠️  Failed to update Google Sheet: {e}")
        import traceback
        traceback.print_exc()


@app.route('/api/accounts/<account_id>/password', methods=['GET'])
def get_account_password(account_id):
    """
    Lấy password và dates của account từ Google Sheet (cột B, C, D)
    """
    try:
        print(f"[PASSWORD API] Getting password for account_id: {account_id}")
        
        if not GOOGLE_SHEETS_AVAILABLE:
            print(f"[PASSWORD API] ❌ Google Sheets API not available")
            return jsonify({
                'success': False,
                'error': 'Google Sheets API not available'
            }), 500
        
        # Lấy account
        account = db.get_account_by_id(account_id)
        if not account:
            print(f"[PASSWORD API] ❌ Account not found")
            return jsonify({'success': False, 'error': 'Account not found'}), 404
        
        email = account['email']
        print(f"[PASSWORD API] Email: {email}")
        
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account.json')
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Bing_1')
        
        print(f"[PASSWORD API] Config: file={service_account_file}, has_json_env={bool(service_account_json)}, sheet_id={sheet_id[:20] if sheet_id else None}..., sheet_name={sheet_name}")
        
        if not sheet_id:
            print(f"[PASSWORD API] ❌ Missing sheet_id")
            return jsonify({
                'success': False,
                'error': 'Missing sheet_id in .env'
            }), 400
        
        # Khởi tạo Google Sheets API
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        
        # Ưu tiên dùng JSON từ environment variable
        if service_account_json:
            print(f"[PASSWORD API] Using credentials from GOOGLE_SERVICE_ACCOUNT_JSON env var")
            import json
            credentials_dict = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict, scopes=SCOPES
            )
        elif os.path.exists(service_account_file):
            print(f"[PASSWORD API] Using credentials from file: {service_account_file}")
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=SCOPES
            )
        else:
            print(f"[PASSWORD API] ❌ No credentials found")
            return jsonify({
                'success': False,
                'error': 'No Google service account credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON env var or provide service-account.json file'
            }), 500
        service = build('sheets', 'v4', credentials=credentials)
        
        print(f"[PASSWORD API] Reading sheet range: {sheet_name}!A2:D1000")
        
        # Đọc cột A, B, C, D để tìm email và lấy password, created_at, updated_at
        range_name = f'{sheet_name}!A2:D1000'
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        print(f"[PASSWORD API] Found {len(values)} rows in sheet")
        
        # Tìm email trong sheet
        password = None
        created_at = None
        updated_at = None
        
        for i, row in enumerate(values):
            if row and len(row) > 0 and row[0].strip() == email:
                print(f"[PASSWORD API] ✅ Found email at row {i+2}")
                # Tìm thấy email
                if len(row) > 1:
                    password = row[1].strip()
                    print(f"[PASSWORD API] Password: {password[:3]}***")
                if len(row) > 2:
                    created_at = row[2].strip()
                    print(f"[PASSWORD API] Created At: {created_at}")
                if len(row) > 3:
                    updated_at = row[3].strip()
                    print(f"[PASSWORD API] Updated At: {updated_at}")
                break
        
        if password:
            print(f"[PASSWORD API] ✅ Success")
            return jsonify({
                'success': True,
                'data': {
                    'password': password,
                    'created_at': created_at,
                    'updated_at': updated_at
                }
            })
        else:
            print(f"[PASSWORD API] ❌ Email not found in sheet")
            return jsonify({
                'success': False,
                'error': 'Password not found in Google Sheet'
            }), 404
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[PASSWORD API] ❌ Exception: {e}")
        print(error_trace)
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': error_trace
        }), 500


@app.route('/api/gsheet/check', methods=['GET'])
def gsheet_check():
    """
    Kiểm tra kết nối Google Sheet và xem dữ liệu
    """
    try:
        if not GOOGLE_SHEETS_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Google Sheets API not available'
            }), 500
        
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account.json')
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Bảng_1')
        
        if not service_account_file or not sheet_id:
            return jsonify({
                'success': False,
                'error': 'Missing service_account_file or sheet_id in .env'
            }), 400
        
        # Khởi tạo Google Sheets API
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        
        # Đọc 100 dòng đầu từ cột A (chỉ cần email)
        range_name = f'{sheet_name}!A2:A100'
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        # Phân tích dữ liệu
        emails_in_sheet = []
        emails_in_db = []
        emails_not_in_db = []
        
        for i, row in enumerate(values, start=2):  # Start từ row 2
            if row and len(row) > 0 and row[0].strip():
                email = row[0].strip()
                
                # Kiểm tra email đã có trong MongoDB chưa
                account = db.get_account_by_email(email)
                
                if account:
                    emails_in_db.append({
                        'row': i,
                        'email': email,
                        'status': account.get('status'),
                        'last_login': account.get('last_login')
                    })
                else:
                    emails_not_in_db.append({
                        'row': i,
                        'email': email
                    })
                
                emails_in_sheet.append(email)
        
        return jsonify({
            'success': True,
            'config': {
                'sheet_id': sheet_id,
                'sheet_name': sheet_name,
                'service_account_file': service_account_file
            },
            'data': {
                'total_emails': len(emails_in_sheet),
                'emails_in_db': len(emails_in_db),
                'emails_not_in_db': len(emails_not_in_db),
                'unprocessed_emails': emails_not_in_db[:10],  # Chỉ show 10 email đầu
                'processed_emails': emails_in_db[:5]  # Chỉ show 5 email đầu
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/gsheet/login-batch', methods=['POST'])
def gsheet_login_batch():
    """
    Đọc email từ Google Sheet (cột A) và login hàng loạt
    Chỉ đọc email, KHÔNG ghi lại vào sheet
    Lưu kết quả vào MongoDB
    """
    try:
        if not GOOGLE_SHEETS_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Google Sheets API not available'
            }), 500
        
        data = request.json
        
        service_account_file = data.get('service_account_file') or os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account.json')
        sheet_id = data.get('sheet_id') or os.getenv('GOOGLE_SHEET_ID')
        sheet_name = data.get('sheet_name') or os.getenv('GOOGLE_SHEET_NAME', 'Bảng_1')
        start_row = data.get('start_row', 2)
        max_rows = data.get('max_rows', 100)
        password = data.get('password', '171004Minh@@')
        account_type = data.get('account_type', 'Team')
        
        if not service_account_file or not sheet_id:
            return jsonify({
                'success': False,
                'error': 'Missing service_account_file or sheet_id'
            }), 400
        
        # Khởi tạo Google Sheets API
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        
        # Đọc email từ cột A (CHỈ cột A)
        range_name = f'{sheet_name}!A{start_row}:A{start_row + max_rows - 1}'
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return jsonify({
                'success': False,
                'error': 'No emails found in sheet'
            }), 400
        
        # Lọc email hợp lệ và chưa có trong MongoDB
        emails_to_process = []
        
        for i, row in enumerate(values):
            if row and len(row) > 0 and row[0].strip():
                email = row[0].strip()
                row_index = start_row + i
                
                # Kiểm tra email đã có trong MongoDB chưa
                account = db.get_account_by_email(email)
                
                # Nếu chưa có hoặc status là pending → Xử lý
                if not account or account.get('status') == 'pending':
                    emails_to_process.append({
                        'email': email,
                        'row_index': row_index
                    })
        
        if not emails_to_process:
            return jsonify({
                'success': True,
                'message': 'All emails already processed',
                'total': 0,
                'processed': 0,
                'failed': 0
            })
        
        # Xử lý từng email
        results = []
        success_count = 0
        fail_count = 0
        
        print(f"\n{'='*70}")
        print(f"BẮT ĐẦU XỬ LÝ {len(emails_to_process)} EMAIL")
        print(f"{'='*70}\n")
        
        for idx, item in enumerate(emails_to_process, 1):
            email = item['email']
            row_index = item['row_index']
            
            print(f"[{idx}/{len(emails_to_process)}] Đang xử lý: {email} (Row {row_index})")
            
            try:
                # Tạo hoặc lấy account
                account = db.get_account_by_email(email)
                if not account:
                    account = db.create_account(email, password, account_type)
                    print(f"  ✓ Đã tạo account trong DB")
                else:
                    print(f"  ✓ Account đã tồn tại trong DB")
                
                account_id = str(account['_id'])
                
                # Login
                db.add_log(account_id, 'gsheet_login_started', f'Starting login from Google Sheet row {row_index}')
                print(f"  → Bắt đầu login...")
                
                login_bot = ChatGPTLoginWithOTP(email=email)
                
                # Step 1-3: Gửi OTP
                print(f"  → Step 1-3: Gửi OTP...")
                if not login_bot.step1_get_providers():
                    raise Exception('Step 1 failed: Cannot get providers')
                if not login_bot.step2_get_csrf():
                    raise Exception('Step 2 failed: Cannot get CSRF token')
                if not login_bot.step3_signin():
                    raise Exception('Step 3 failed: Cannot signin')
                
                # Step 4: Lấy OTP
                print(f"  → Step 4: Đang lấy OTP từ TempMail...")
                otp_code = login_bot.step4_get_otp(max_attempts=24)
                
                if not otp_code:
                    raise Exception('Failed to get OTP from email')
                
                print(f"  ✓ Đã lấy OTP: {otp_code}")
                
                # Step 5: Validate OTP
                print(f"  → Step 5: Validate OTP...")
                validate_result = login_bot.step5_validate_otp(otp_code)
                
                if validate_result == 'banned':
                    raise Exception('Account is banned/deactivated')
                
                if not validate_result:
                    raise Exception('OTP validation failed')
                
                print(f"  ✓ OTP hợp lệ")
                
                # Step 6-8: Lấy thông tin
                print(f"  → Step 6-8: Lấy thông tin account...")
                if not login_bot.step6_get_session():
                    raise Exception('Step 6 failed: Cannot get session')
                
                # Debug: Kiểm tra dữ liệu trước khi lưu
                print(f"  → Debug: Checking session data...")
                print(f"     Access Token: {login_bot.access_token[:50] if login_bot.access_token else 'None'}...")
                print(f"     User ID: {login_bot.user_id}")
                print(f"     Account ID: {login_bot.account_id}")
                print(f"     Cookies count: {len(login_bot.session.cookies)}")
                
                # Lưu session vào MongoDB
                session_data = {
                    'access_token': login_bot.access_token,
                    'user_id': login_bot.user_id,
                    'account_id': login_bot.account_id
                }
                
                # QUAN TRỌNG: curl_cffi 0.5.10 throw exception khi có duplicate cookies
                # Phải access cookies ở low level để tránh exception
                cookies = {}
                print(f"  → Debug: Extracting cookies...")
                
                try:
                    # Access internal cookie jar để tránh duplicate check
                    if hasattr(login_bot.session.cookies, 'jar'):
                        # Có internal jar
                        for cookie in login_bot.session.cookies.jar:
                            cookie_key = cookie.name
                            if cookie.domain:
                                cookie_key = f"{cookie.name}@{cookie.domain}"
                            cookies[cookie_key] = cookie.value
                    elif hasattr(login_bot.session.cookies, '_cookies'):
                        # Access _cookies dict trực tiếp
                        for domain, paths in login_bot.session.cookies._cookies.items():
                            for path, names in paths.items():
                                for name, cookie in names.items():
                                    cookie_key = f"{name}@{domain}"
                                    cookies[cookie_key] = cookie.value
                    else:
                        # Fallback: iterate manually
                        cookie_list = list(login_bot.session.cookies)
                        for cookie in cookie_list:
                            cookie_key = cookie.name
                            if hasattr(cookie, 'domain') and cookie.domain:
                                cookie_key = f"{cookie.name}@{cookie.domain}"
                            cookies[cookie_key] = cookie.value
                except Exception as e:
                    print(f"  ⚠️  Error extracting cookies: {e}")
                    # Last resort: empty cookies
                    cookies = {}
                
                print(f"  → Debug: Extracted {len(cookies)} cookies")
                
                # Debug: Hiển thị cookies
                print(f"  → Debug: Cookies to save:")
                for cookie_name in list(cookies.keys())[:5]:  # Show first 5
                    print(f"     - {cookie_name}: {cookies[cookie_name][:30]}...")
                
                # Lưu vào DB
                print(f"  → Saving to MongoDB...")
                save_result = db.save_session(account_id, session_data, cookies)
                
                if save_result:
                    print(f"  ✓ Đã lưu session vào MongoDB")
                    
                    # Verify: Đọc lại từ DB
                    print(f"  → Verifying: Reading back from DB...")
                    saved_session = db.get_session(account_id)
                    if saved_session:
                        print(f"     ✓ Verified: Found session in DB")
                        print(f"     ✓ Cookies in DB: {len(saved_session.get('cookies', {}))}")
                    else:
                        print(f"     ❌ WARNING: Session not found in DB after save!")
                else:
                    print(f"  ❌ WARNING: save_session returned False!")
                
                # Update account
                db.update_account_status(account_id, 'active')
                
                me_data = login_bot.step7_get_me()
                if me_data:
                    db.update_account(account_id, {
                        'user_id': me_data.get('id'),
                        'name': me_data.get('name'),
                        'email_verified': me_data.get('email_verified')
                    })
                    print(f"  ✓ Đã cập nhật thông tin user")
                
                sub_data = login_bot.step8_get_subscription()
                if sub_data:
                    db.update_account_subscription(account_id, sub_data)
                    print(f"  ✓ Đã cập nhật subscription")
                    
                    # Detect account_type: chỉ có 2 loại - Personal hoặc Team
                    plan_type = sub_data.get('plan_type', '').lower()
                    if 'team' in plan_type or 'business' in plan_type or 'enterprise' in plan_type:
                        db.update_account(account_id, {'account_type': 'Team'})
                        print(f"  ✓ Account type: Team")
                    else:
                        # Plus, Free, hoặc bất kỳ loại nào khác → Personal
                        db.update_account(account_id, {'account_type': 'Personal'})
                        print(f"  ✓ Account type: Personal")
                
                # Step 9: Lấy số lượng users trong workspace
                users_data = login_bot.step9_get_workspace_users()
                if users_data:
                    total_users = users_data.get('total', 0)
                    db.update_account(account_id, {'total_users': total_users})
                    print(f"  ✓ Đã cập nhật số lượng users: {total_users}")
                else:
                    # Nếu không lấy được users (có thể là tài khoản Personal), set total_users = 1
                    db.update_account(account_id, {'total_users': 1})
                    print(f"  ✓ Tài khoản Personal, set total_users = 1")
                
                db.add_log(account_id, 'gsheet_login_success', f'Login successful from sheet row {row_index}')
                
                results.append({
                    'email': email,
                    'row_index': row_index,
                    'status': 'success',
                    'account_id': account_id
                })
                
                success_count += 1
                print(f"  ✅ THÀNH CÔNG!\n")
                
            except Exception as e:
                error_msg = str(e)
                print(f"  ❌ THẤT BẠI: {error_msg}")
                
                # Log traceback for debugging
                import traceback
                traceback.print_exc()
                print()
                
                if 'account_id' in locals():
                    # Check if account is banned
                    if 'banned' in error_msg.lower() or 'deactivated' in error_msg.lower():
                        db.update_account_status(account_id, 'banned')
                        print(f"  🚫 Account đã được đánh dấu là BANNED")
                        
                        # Update Google Sheet cột G
                        update_google_sheet_status(email, ban_status='banned')
                    
                    db.add_log(account_id, 'gsheet_login_failed', error_msg, 'error')
                
                results.append({
                    'email': email,
                    'row_index': row_index,
                    'status': 'failed',
                    'error': error_msg
                })
                
                fail_count += 1
        
        print(f"\n{'='*70}")
        print(f"KẾT QUẢ: Thành công {success_count}/{len(emails_to_process)}, Thất bại {fail_count}/{len(emails_to_process)}")
        print(f"{'='*70}\n")
        
        return jsonify({
            'success': True,
            'message': f'Processed {len(emails_to_process)} emails',
            'total': len(emails_to_process),
            'processed': success_count,
            'failed': fail_count,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Run App
# ============================================

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    print("="*70)
    print("🚀 ChatGPT Account Manager")
    print("="*70)
    print(f"📍 URL: http://localhost:{port}")
    print(f"🔧 Debug: {debug}")
    print("="*70)
    
    app.run(host='0.0.0.0', port=port, debug=debug)

