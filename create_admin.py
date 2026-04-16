from transportapp import app
from app import db
from app.models import User

with app.app_context():
    # Ищем админа по имени
    admin = User.query.filter_by(username='admin').first()
    
    if not admin:
        # Добавляем email, чтобы не срабатывал NOT NULL constraint
        admin = User(
            username='admin', 
            email='admin@example.com',  # Добавь эту строку
            is_admin=True,               # Проверь, как называется поле в модели (is_admin или role)
            default_region_code='00',
            default_carrier_id='0000',
            default_unit_id='0000'
        )
        admin.set_password('admin_iset')
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully!")
    else:
        print("Admin already exists.")