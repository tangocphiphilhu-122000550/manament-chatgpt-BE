"""
MongoDB Database Manager cho ChatGPT Account Management
"""

import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import certifi

load_dotenv()


class DatabaseManager:
    def __init__(self):
        """Khởi tạo kết nối MongoDB"""
        mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        
        print(f"[DB] Connecting to MongoDB...")
        print(f"[DB] URI type: {'Atlas (SRV)' if 'mongodb+srv' in mongodb_uri else 'Atlas' if 'mongodb.net' in mongodb_uri else 'Local'}")
        
        try:
            # Đơn giản hóa connection - chỉ dùng URI với minimal params
            if 'mongodb+srv' in mongodb_uri:
                # MongoDB Atlas với SRV (cần dnspython)
                print(f"[DB] Using SRV connection with SSL bypass...")
                
                # Thêm params vào URI để bypass SSL verification
                if '?' not in mongodb_uri:
                    mongodb_uri += '?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true'
                elif 'tlsAllowInvalidCertificates' not in mongodb_uri:
                    mongodb_uri += '&tls=true&tlsAllowInvalidCertificates=true'
                
                print(f"[DB] Connection params: tls=true, tlsAllowInvalidCertificates=true")
                
                self.client = MongoClient(
                    mongodb_uri,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )
            elif 'mongodb.net' in mongodb_uri:
                # MongoDB Atlas không SRV
                print(f"[DB] Using standard connection with SSL bypass...")
                
                if '?' not in mongodb_uri:
                    mongodb_uri += '?tls=true&tlsAllowInvalidCertificates=true'
                elif 'tlsAllowInvalidCertificates' not in mongodb_uri:
                    mongodb_uri += '&tls=true&tlsAllowInvalidCertificates=true'
                
                self.client = MongoClient(
                    mongodb_uri,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000
                )
            else:
                # Local MongoDB
                print(f"[DB] Using local connection...")
                self.client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            
            # Test connection
            print(f"[DB] Testing connection with ping...")
            self.client.admin.command('ping')
            print(f"[DB] ✅ MongoDB connection successful!")
            
            self.db = self.client[os.getenv('MONGODB_DB', 'chatgpt_manager')]
            
            # Collections
            self.accounts = self.db['accounts']
            self.sessions = self.db['sessions']
            self.logs = self.db['logs']
            
            # Tạo indexes (với error handling)
            self._create_indexes()
            
            print(f"✅ Đã kết nối MongoDB: {os.getenv('MONGODB_DB')}")
            
        except Exception as e:
            print(f"[DB] ❌ MongoDB connection failed: {e}")
            print(f"[DB] Error type: {type(e).__name__}")
            print(f"[DB] ⚠️  App will start but database operations will fail")
            import traceback
            traceback.print_exc()
            
            # Set dummy values để app không crash
            self.client = None
            self.db = None
            self.accounts = None
            self.sessions = None
            self.logs = None
    
    def _create_indexes(self):
        """Tạo indexes cho collections"""
        try:
            # Index cho accounts
            self.accounts.create_index('email', unique=True)
            self.accounts.create_index('status')
            self.accounts.create_index('created_at')
            
            # Index cho sessions
            self.sessions.create_index('account_id')
            self.sessions.create_index('expires_at')
            
            # Index cho logs
            self.logs.create_index('account_id')
            self.logs.create_index('created_at')
            
            print("✅ Đã tạo indexes")
        except Exception as e:
            print(f"⚠️  Warning: Could not create indexes: {e}")
            # Không raise exception, cho phép app chạy tiếp
    
    # ============================================
    # ACCOUNTS CRUD
    # ============================================
    
    def create_account(self, email, password, account_type='Team', source='mailp.tech'):
        """
        Tạo account mới
        
        Args:
            email: Email account
            password: Password
            account_type: Loại account (Team/Personal)
            source: Nguồn email
            
        Returns:
            dict: Account document hoặc None nếu lỗi
        """
        try:
            account = {
                'email': email,
                'password': password,
                'account_type': account_type,
                'source': source,
                'status': 'pending',  # pending, active, banned, expired
                'workspaces': [],
                'subscription': {},
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'last_login': None,
                'ban_status': 'No ban',
                'notes': ''
            }
            
            result = self.accounts.insert_one(account)
            account['_id'] = result.inserted_id
            
            # Log
            self.add_log(str(result.inserted_id), 'account_created', f'Account {email} created')
            
            return account
            
        except Exception as e:
            print(f"❌ Lỗi khi tạo account: {e}")
            return None
    
    def get_account_by_email(self, email):
        """Lấy account theo email"""
        return self.accounts.find_one({'email': email})
    
    def get_account_by_id(self, account_id):
        """Lấy account theo ID"""
        from bson.objectid import ObjectId
        return self.accounts.find_one({'_id': ObjectId(account_id)})
    
    def get_all_accounts(self, status=None, limit=100, skip=0):
        """
        Lấy danh sách accounts
        
        Args:
            status: Lọc theo status (None = all)
            limit: Số lượng tối đa
            skip: Bỏ qua số lượng
            
        Returns:
            list: Danh sách accounts
        """
        query = {}
        if status:
            query['status'] = status
        
        return list(self.accounts.find(query).sort('created_at', -1).limit(limit).skip(skip))
    
    def update_account(self, account_id, update_data):
        """
        Cập nhật account
        
        Args:
            account_id: ID của account
            update_data: Dict chứa dữ liệu cần update
            
        Returns:
            bool: True nếu thành công
        """
        try:
            from bson.objectid import ObjectId
            
            update_data['updated_at'] = datetime.utcnow()
            
            result = self.accounts.update_one(
                {'_id': ObjectId(account_id)},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                self.add_log(account_id, 'account_updated', f'Account updated: {list(update_data.keys())}')
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Lỗi khi update account: {e}")
            return False
    
    def update_account_status(self, account_id, status):
        """Cập nhật status của account"""
        return self.update_account(account_id, {'status': status})
    
    def update_account_workspaces(self, account_id, workspaces):
        """Cập nhật danh sách workspace"""
        return self.update_account(account_id, {'workspaces': workspaces})
    
    def update_account_subscription(self, account_id, subscription):
        """Cập nhật thông tin subscription"""
        return self.update_account(account_id, {'subscription': subscription})
    
    def delete_account(self, account_id):
        """Xóa account"""
        try:
            from bson.objectid import ObjectId
            
            # Xóa sessions liên quan
            self.sessions.delete_many({'account_id': account_id})
            
            # Xóa account
            result = self.accounts.delete_one({'_id': ObjectId(account_id)})
            
            if result.deleted_count > 0:
                self.add_log(account_id, 'account_deleted', 'Account deleted')
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Lỗi khi xóa account: {e}")
            return False
    
    def count_accounts(self, status=None):
        """Đếm số lượng accounts"""
        query = {}
        if status:
            query['status'] = status
        return self.accounts.count_documents(query)
    
    # ============================================
    # SESSIONS CRUD
    # ============================================
    
    def save_session(self, account_id, session_data, cookies, expires_days=30):
        """
        Lưu session của account
        
        Args:
            account_id: ID của account
            session_data: Dict chứa session data (access_token, user_id, etc.)
            cookies: Dict chứa cookies
            expires_days: Số ngày hết hạn
            
        Returns:
            bool: True nếu thành công
        """
        try:
            from datetime import timedelta
            
            print(f"[DB] save_session called for account_id: {account_id}")
            print(f"[DB] session_data keys: {list(session_data.keys())}")
            print(f"[DB] cookies count: {len(cookies)}")
            
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
            
            session = {
                'account_id': account_id,
                'session_data': session_data,
                'cookies': cookies,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at,
                'is_valid': True
            }
            
            print(f"[DB] Deleting old sessions for account_id: {account_id}")
            # Xóa session cũ
            delete_result = self.sessions.delete_many({'account_id': account_id})
            print(f"[DB] Deleted {delete_result.deleted_count} old sessions")
            
            print(f"[DB] Inserting new session...")
            # Tạo session mới
            insert_result = self.sessions.insert_one(session)
            print(f"[DB] Inserted session with _id: {insert_result.inserted_id}")
            
            # Update last_login
            self.update_account(account_id, {'last_login': datetime.utcnow()})
            
            self.add_log(account_id, 'session_saved', 'Session saved')
            
            print(f"[DB] save_session completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ [DB] Lỗi khi lưu session: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_session(self, account_id):
        """Lấy session của account"""
        return self.sessions.find_one({
            'account_id': account_id,
            'is_valid': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
    
    def invalidate_session(self, account_id):
        """Vô hiệu hóa session"""
        try:
            result = self.sessions.update_many(
                {'account_id': account_id},
                {'$set': {'is_valid': False}}
            )
            
            if result.modified_count > 0:
                self.add_log(account_id, 'session_invalidated', 'Session invalidated')
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Lỗi khi invalidate session: {e}")
            return False
    
    def cleanup_expired_sessions(self):
        """Xóa các session đã hết hạn"""
        try:
            result = self.sessions.delete_many({
                'expires_at': {'$lt': datetime.utcnow()}
            })
            
            print(f"🗑️  Đã xóa {result.deleted_count} session hết hạn")
            return result.deleted_count
            
        except Exception as e:
            print(f"❌ Lỗi khi cleanup sessions: {e}")
            return 0
    
    # ============================================
    # LOGS
    # ============================================
    
    def add_log(self, account_id, action, message, level='info'):
        """
        Thêm log
        
        Args:
            account_id: ID của account
            action: Hành động (account_created, login_success, etc.)
            message: Nội dung log
            level: info, warning, error
        """
        try:
            log = {
                'account_id': account_id,
                'action': action,
                'message': message,
                'level': level,
                'created_at': datetime.utcnow()
            }
            
            self.logs.insert_one(log)
            
        except Exception as e:
            print(f"⚠️  Lỗi khi ghi log: {e}")
    
    def get_logs(self, account_id=None, limit=100):
        """Lấy logs"""
        query = {}
        if account_id:
            query['account_id'] = account_id
        
        return list(self.logs.find(query).sort('created_at', -1).limit(limit))
    
    # ============================================
    # STATISTICS
    # ============================================
    
    def get_statistics(self):
        """Lấy thống kê tổng quan"""
        if not self.client:
            raise Exception("MongoDB not connected")
        
        return {
            'total_accounts': self.count_accounts(),
            'active_accounts': self.count_accounts('active'),
            'pending_accounts': self.count_accounts('pending'),
            'banned_accounts': self.count_accounts('banned'),
            'expired_accounts': self.count_accounts('expired'),
            'total_sessions': self.sessions.count_documents({'is_valid': True}),
            'total_logs': self.logs.count_documents({})
        }


# Singleton instance
db = DatabaseManager()
