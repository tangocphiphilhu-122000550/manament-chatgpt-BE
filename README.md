# Backend - ChatGPT Account Manager

Backend API sử dụng Flask + MongoDB để quản lý tài khoản ChatGPT.

## Cài đặt

### 1. Cài đặt Python dependencies

```bash
cd be
pip install -r requirements.txt
```

### 2. Cài đặt MongoDB

**Windows:**
- Download: https://www.mongodb.com/try/download/community
- Hoặc dùng MongoDB Atlas (cloud): https://www.mongodb.com/cloud/atlas

**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Linux:**
```bash
sudo apt-get install mongodb
sudo systemctl start mongodb
```

### 3. Cấu hình

Copy file `.env.example` thành `.env` và cập nhật:

```bash
cp .env.example .env
```

Sửa file `.env`:
```env
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=chatgpt_manager
TEMPMAIL_API_KEY=your-tempmail-api-key
FLASK_SECRET_KEY=your-secret-key
```

## Chạy server

```bash
python app.py
```

Server sẽ chạy tại: http://localhost:5000

## API Endpoints

### Statistics
- `GET /api/statistics` - Lấy thống kê tổng quan

### Accounts
- `GET /api/accounts` - Lấy danh sách accounts
- `GET /api/accounts/:id` - Lấy thông tin account
- `POST /api/accounts` - Tạo account mới
- `PUT /api/accounts/:id` - Cập nhật account
- `DELETE /api/accounts/:id` - Xóa account

### Login
- `POST /api/login` - Gửi OTP đến email
- `POST /api/login/verify-otp` - Verify OTP và hoàn tất login
- `POST /api/login/auto-otp` - Tự động lấy OTP và login

### Sessions
- `GET /api/sessions/:account_id` - Lấy session
- `DELETE /api/sessions/:account_id` - Xóa session

### Logs
- `GET /api/logs?account_id=xxx` - Lấy logs

## Database Schema

### Accounts Collection
```javascript
{
  _id: ObjectId,
  email: String,
  password: String,
  account_type: String, // 'Team' or 'Personal'
  source: String,
  status: String, // 'pending', 'active', 'banned', 'expired'
  workspaces: Array,
  subscription: Object,
  created_at: Date,
  updated_at: Date,
  last_login: Date,
  ban_status: String,
  notes: String
}
```

### Sessions Collection
```javascript
{
  _id: ObjectId,
  account_id: String,
  session_data: {
    access_token: String,
    user_id: String,
    account_id: String
  },
  cookies: Object,
  created_at: Date,
  expires_at: Date,
  is_valid: Boolean
}
```

### Logs Collection
```javascript
{
  _id: ObjectId,
  account_id: String,
  action: String,
  message: String,
  level: String, // 'info', 'warning', 'error'
  created_at: Date
}
```

## Scripts

### Login với Google Sheet
```bash
python login_with_gsheet.py
```

Đọc email từ Google Sheet và tự động login.

## Troubleshooting

### MongoDB connection error
- Kiểm tra MongoDB đã chạy: `mongosh` hoặc `mongo`
- Kiểm tra MONGODB_URI trong `.env`

### TempMail API error
- Kiểm tra TEMPMAIL_API_KEY trong `.env`
- Verify API key còn hoạt động

### Import error
- Chạy: `pip install -r requirements.txt`
