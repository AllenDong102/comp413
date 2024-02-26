from db import User


class SessionUser:
    user: User
    is_authenticated: bool
    is_active: bool
    is_anonymous: bool

    def __init__(self, user, is_authenticated, is_active, is_anonymous):
        self.user = user
        self.is_authenticated = is_authenticated
        self.is_active = is_active
        self.is_anonymous = is_anonymous

    def get_id(self):
        return self.user.id
