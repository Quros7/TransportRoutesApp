from decimal import Decimal

from werkzeug.datastructures import FileStorage, ImmutableMultiDict

from app.forms import BulkGenerateForm, EditProfileForm, ImportRouteForm, LoginForm, RegistrationForm, RouteInfoForm, RoutePricesForm, RouteStopsForm, StopForm, TariffTableEntryForm


class TestLoginForm:
    def test_login_form_valid(self, app):
        with app.app_context():
            form = LoginForm(username="testuser", password="password", remember_me=True)
            assert form.validate() is True

    def test_login_form_invalid_missing_username(self, app):
        with app.app_context():
            form = LoginForm(password="password")
            assert form.validate() is False
            assert "This field is required" in str(form.username.errors)

    def test_login_form_invalid_missing_password(self, app):
        with app.app_context():
            form = LoginForm(username="testuser")
            assert form.validate() is False
            assert "This field is required" in str(form.password.errors)


class TestRegistrationForm:
    def test_registration_form_valid(self, app):
        with app.app_context():
            form = RegistrationForm(
                username="newuser",
                email="new@example.com",
                password="password",
                password2="password",
            )
            assert form.validate() is True

    def test_registration_form_invalid_username_taken(self, app, test_user):
        with app.app_context():
            form = RegistrationForm(
                username="testuser",
                email="new@example.com",
                password="password",
                password2="password",
            )
            assert form.validate() is False
            assert "Это имя уже занято" in str(form.username.errors)

    def test_registration_form_invalid_email_taken(self, app, test_user):
        with app.app_context():
            form = RegistrationForm(
                username="newuser",
                email="test@example.com",
                password="password",
                password2="password",
            )
            assert form.validate() is False
            assert "Этот email адрес уже занят" in str(form.email.errors)

    def test_registration_form_invalid_password_mismatch(self, app):
        with app.app_context():
            form = RegistrationForm(
                username="newuser",
                email="new@example.com",
                password="password",
                password2="different",
            )
            assert form.validate() is False
            assert "Пароли не совпадают" in str(form.password2.errors)


class TestTariffTableEntryForm:
    def test_tariff_table_form_valid_first_table(self, app):
        with app.app_context():
            form = TariffTableEntryForm(
                tariff_name="Test Tariff",
                table_type_code="02",
                ss_series_codes="01;02",
            )
            assert form.validate() is True

    def test_tariff_table_form_valid_subsequent_table(self, app):
        with app.app_context():
            form = TariffTableEntryForm(
                tariff_name="Test Tariff 2",
                table_type_code="P",
                ss_series_codes="03",
            )
            assert form.validate() is True

    def test_tariff_table_form_invalid_table_type_code(self, app):
        with app.app_context():
            form = TariffTableEntryForm(
                tariff_name="Test Tariff",
                table_type_code="03",
                ss_series_codes="01",
            )
            assert form.validate() is False
            assert 'Допускается только "02"' in str(form.table_type_code.errors)

    def test_tariff_table_form_invalid_ss_series_format(self, app):
        with app.app_context():
            form = TariffTableEntryForm(
                tariff_name="Test Tariff",
                table_type_code="02",
                ss_series_codes="abc;def",
            )
            assert form.validate() is False
            assert "Введите коды серий SS" in str(form.ss_series_codes.errors)


class TestStopForm:
    def test_stop_form_valid(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict([("stop_name", "Test Stop"), ("km_distance", "10.50")])
            form = StopForm(formdata=formdata)
            assert form.validate() is True

    def test_stop_form_invalid_negative_distance(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict([("stop_name", "Test Stop"), ("km_distance", "-1.00")])
            form = StopForm(formdata=formdata)
            assert form.validate() is False
            assert "Расстояние не может быть отрицательным" in str(form.km_distance.errors)

    def test_stop_form_invalid_too_many_decimals(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict([("stop_name", "Test Stop"), ("km_distance", "10.123")])
            form = StopForm(formdata=formdata)
            assert form.validate() is False
            assert "не более двух знаков после запятой" in str(form.km_distance.errors)

    def test_stop_form_invalid_exceeds_max(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict([("stop_name", "Test Stop"), ("km_distance", "100.00")])
            form = StopForm(formdata=formdata)
            assert form.validate() is False
            assert "не может превышать 99.99 км" in str(form.km_distance.errors)


class TestRouteInfoForm:
    def test_route_info_form_valid(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("region_code", "66"),
                    ("carrier_id", "7012"),
                    ("unit_id", "0001"),
                    ("decimal_places", "2"),
                    ("route_name", "Test Route"),
                    ("route_number", "854"),
                    ("transport_type", "0x02"),
                    ("tariff_tables-0-tariff_name", "Test Tariff"),
                    ("tariff_tables-0-table_type_code", "02"),
                    ("tariff_tables-0-ss_series_codes", "01"),
                ]
            )
            form = RouteInfoForm(formdata=formdata)
            assert form.validate() is True

    def test_route_info_form_invalid_tariff_table_validation(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("region_code", "66"),
                    ("carrier_id", "7012"),
                    ("unit_id", "0001"),
                    ("decimal_places", "2"),
                    ("route_name", "Test Route"),
                    ("route_number", "854"),
                    ("transport_type", "0x02"),
                    ("tariff_tables-0-tariff_name", "Test Tariff"),
                    ("tariff_tables-0-table_type_code", "P"),  # Invalid for first table
                    ("tariff_tables-0-ss_series_codes", "01"),
                ]
            )
            form = RouteInfoForm(formdata=formdata)
            assert form.validate() is False
            assert 'Таблица 1 должна начинаться с кода "02"' in str(form.tariff_tables.errors)

    def test_route_info_form_invalid_duplicate_ss_codes(self, app):
        with app.app_context():
            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("region_code", "66"),
                    ("carrier_id", "7012"),
                    ("unit_id", "0001"),
                    ("decimal_places", "2"),
                    ("route_name", "Test Route"),
                    ("route_number", "854"),
                    ("transport_type", "0x02"),
                    ("tariff_tables-0-tariff_name", "Test Tariff 1"),
                    ("tariff_tables-0-table_type_code", "02"),
                    ("tariff_tables-0-ss_series_codes", "01"),
                    ("tariff_tables-1-tariff_name", "Test Tariff 2"),
                    ("tariff_tables-1-table_type_code", "P"),
                    ("tariff_tables-1-ss_series_codes", "01"),  # Duplicate
                ]
            )
            form = RouteInfoForm(formdata=formdata)
            assert form.validate() is False
            assert "уже присутствует в другой таблице" in str(form.tariff_tables.errors)


class TestRouteStopsForm:
    def test_route_stops_form_valid_city_route(self, app):
        with app.app_context():
            # City route should accept exactly one stop.
            class MockRoute:
                transport_type = "0x02"

            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("stops-0-stop_name", "Stop 1"),
                    ("stops-0-km_distance", "0.00"),
                ]
            )
            form = RouteStopsForm(formdata=formdata, route=MockRoute())
            assert form.validate() is True

    def test_route_stops_form_valid_intercity_route(self, app):
        with app.app_context():
            # Non-city route (e.g. 0x40) should allow multiple stops.
            class MockRoute:
                transport_type = "0x40"

            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("stops-0-stop_name", "Stop 1"),
                    ("stops-0-km_distance", "0.00"),
                    ("stops-1-stop_name", "Stop 2"),
                    ("stops-1-km_distance", "10.00"),
                ]
            )
            form = RouteStopsForm(formdata=formdata, route=MockRoute())
            assert form.validate() is True

    def test_route_stops_form_invalid_city_route_multiple_stops(self, app):
        with app.app_context():

            class MockRoute:
                transport_type = "0x02"

            form = RouteStopsForm(route=MockRoute())
            form.stops.append_entry()
            form.stops[0].stop_name = "Stop 1"
            form.stops[0].km_distance = Decimal("0.00")
            form.stops.append_entry()
            form.stops[1].stop_name = "Stop 2"
            form.stops[1].km_distance = Decimal("10.00")
            assert form.validate() is False
            assert "Городской маршрут может содержать только одну зону" in str(form.stops.errors)

    def test_route_stops_form_invalid_non_city_route_single_stop(self, app):
        with app.app_context():

            class MockRoute:
                transport_type = "0x20"

            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("stops-0-stop_name", "Stop 1"),
                    ("stops-0-km_distance", "0.00"),
                ]
            )
            form = RouteStopsForm(formdata=formdata, route=MockRoute())
            assert form.validate() is False
            assert "минимум 2 остановки" in str(form.stops.errors)

    def test_route_stops_form_invalid_non_increasing_distances(self, app):
        with app.app_context():

            class MockRoute:
                transport_type = "0x20"

            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("stops-0-stop_name", "Stop 1"),
                    ("stops-0-km_distance", "0.00"),
                    ("stops-1-stop_name", "Stop 2"),
                    ("stops-1-km_distance", "5.00"),
                    ("stops-2-stop_name", "Stop 3"),
                    ("stops-2-km_distance", "3.00"),  # Decreasing
                ]
            )
            form = RouteStopsForm(formdata=formdata, route=MockRoute())
            assert form.validate() is False
            assert "должно быть строго больше" in str(form.stops.errors)

    def test_route_stops_form_invalid_first_stop_not_zero(self, app):
        with app.app_context():

            class MockRoute:
                transport_type = "0x20"

            from werkzeug.datastructures import ImmutableMultiDict

            formdata = ImmutableMultiDict(
                [
                    ("stops-0-stop_name", "Stop 1"),
                    ("stops-0-km_distance", "5.00"),  # Not zero
                    ("stops-1-stop_name", "Stop 2"),
                    ("stops-1-km_distance", "10.00"),
                ]
            )
            form = RouteStopsForm(formdata=formdata, route=MockRoute())
            assert form.validate() is False
            assert "Расстояние до начальной остановки" in str(form.stops.errors)


class TestRoutePricesForm:
    def test_route_prices_form_valid(self, app):
        with app.app_context():
            form = RoutePricesForm(price_matrix_data='{"test": "data"}')
            assert form.validate() is True

    def test_route_prices_form_empty_data(self, app):
        with app.app_context():
            form = RoutePricesForm(price_matrix_data="")
            assert form.validate() is True  # Hidden field, no DataRequired


class TestBulkGenerateForm:
    def test_bulk_generate_form_valid(self, app):
        with app.app_context():
            form = BulkGenerateForm(
                region_code="66",
                carrier_id="7012",
                unit_id="0001",
                decimal_places="2",
            )
            assert form.validate() is True

    def test_bulk_generate_form_invalid_region_code(self, app):
        with app.app_context():
            form = BulkGenerateForm(
                region_code="abc",
                carrier_id="7012",
                unit_id="0001",
                decimal_places="2",
            )
            assert form.validate() is False
            assert "Код должен содержать только цифры" in str(form.region_code.errors)


class TestEditProfileForm:
    def test_edit_profile_form_valid(self, app):
        with app.app_context():
            form = EditProfileForm(
                default_region_code="66",
                default_carrier_id="7012",
                default_unit_id="0001",
            )
            assert form.validate() is True

    def test_edit_profile_form_invalid_carrier_id(self, app):
        with app.app_context():
            form = EditProfileForm(
                default_region_code="66",
                default_carrier_id="abcd",  # Non-numeric
                default_unit_id="0001",
            )
            assert form.validate() is False
            assert "ID должен содержать только цифры" in str(form.default_carrier_id.errors)


class TestImportRouteForm:
    def test_import_route_form_valid(self, app):
        with app.app_context():
            # Create a mock file upload
            from io import BytesIO

            file_data = BytesIO(b"test content")
            file_storage = FileStorage(stream=file_data, filename="test.txt", content_type="text/plain")

            formdata = ImmutableMultiDict([("route_file", file_storage)])
            form = ImportRouteForm(formdata=formdata)
            assert form.validate() is True

    def test_import_route_form_invalid_file_type(self, app):
        with app.app_context():
            from io import BytesIO

            file_data = BytesIO(b"test content")
            file_storage = FileStorage(stream=file_data, filename="test.jpg", content_type="image/jpeg")

            formdata = ImmutableMultiDict([("route_file", file_storage)])
            form = ImportRouteForm(formdata=formdata)
            assert form.validate() is False
            assert "Только текстовые файлы" in str(form.route_file.errors)
