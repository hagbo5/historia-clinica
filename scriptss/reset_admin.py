from index import db, User

def reset_admin_password():
    user = User.query.filter_by(username="admin").first()
    if user:
        user.set_password("123456")
        db.session.commit()
        print("Contraseña actualizada exitosamente.")
    else:
        print("No se encontró el usuario 'admin'.")

if __name__ == "__main__":
    reset_admin_password()
