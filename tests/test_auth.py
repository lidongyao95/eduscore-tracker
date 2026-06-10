class TestAuth:

    def test_login_page_loads(self, client):
        """GET /login returns 200"""
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_login_success(self, client, teacher_id):
        """POST /login with correct credentials redirects and sets session"""
        resp = client.post('/login', data={
            'username': 'teacher',
            'password': 'teacher123'
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should be redirected to admin dashboard
        assert resp.request.path == '/admin/dashboard'

    def test_login_failure(self, client, teacher_id):
        """POST /login with wrong password shows flash message"""
        resp = client.post('/login', data={
            'username': 'teacher',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert resp.status_code == 200
        # The response should contain the error flash message
        assert '用户名或密码错误'.encode('utf-8') in resp.data

    def test_logout(self, client, teacher_id):
        """Login then GET /logout redirects to login page"""
        # Login first
        client.post('/login', data={
            'username': 'teacher',
            'password': 'teacher123'
        }, follow_redirects=True)
        # Then logout
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
        assert resp.request.path == '/login'

    def test_protected_page_without_login(self, client):
        """GET /student/dashboard without login redirects to login"""
        resp = client.get('/student/dashboard', follow_redirects=True)
        assert resp.status_code == 200
        assert resp.request.path == '/login'
