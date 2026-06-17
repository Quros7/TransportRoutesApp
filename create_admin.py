import os

from transportapp import app
from app import db
from app.models import User

with app.app_context():
    # Ищем админа по имени
    admin = User.query.filter_by(username='admin').first()
    
    if not admin:
        # Извлекаем пароль из переменных окружения
        admin_password = os.environ.get('ADMIN_PASSWORD')

        if not admin_password:
            raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменная окружения ADMIN_PASSWORD не задана!")
        
        admin = User(
            username='admin', 
            email='admin@example.com',  # Добавляем email, чтобы не срабатывал NOT NULL constraint
            is_admin=True,              
            default_region_code='00',
            default_carrier_id='0000',
            default_unit_id='0000'
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print("Главный администратор (admin) создан успешно!")
    else:
        print("Главный администратор (admin) уже существует.")