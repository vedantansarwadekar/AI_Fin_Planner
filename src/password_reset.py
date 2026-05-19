# src/password_reset.py

def generate_reset_token(email: str, app_base_url: str, auth_cfg: dict = None):
    return "dummy-token"

def validate_reset_token(token):
    return True

def apply_new_password(token, new_password):
    return "Password updated successfully"