from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SubmitField


# Форма импорта маршрута из файла конфигурации
class ImportRouteForm(FlaskForm):
    route_file = FileField(
        "Выберите файл конфигурации",
        validators=[
            FileRequired(),
            # FileAllowed(["txt"], "Только текстовые файлы конфигурации!"),
        ],
    )
    submit = SubmitField("Загрузить и импортировать")
