from app import db
from app.models import Route


def test_index_redirects_to_login_when_not_logged_in(client):
    response = client.get("/")
    assert response.status_code == 302  # Redirect to login
    assert "/login" in response.headers["Location"]


def test_index_accessible_when_logged_in(logged_in_client):
    response = logged_in_client.get("/")
    assert response.status_code == 200
    assert "Главная" in response.get_data(as_text=True)


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Авторизация" in response.get_data(as_text=True)


def test_login_success(client, test_user):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "password", "remember_me": False},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Главная" in response.get_data(as_text=True)


def test_login_failure(client):
    response = client.post("/login", data={"username": "wrong", "password": "wrong"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Неверный логин или пароль" in response.get_data(as_text=True)


def test_logout(logged_in_client):
    response = logged_in_client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert "Главная" in response.get_data(as_text=True)


def test_register_page(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert "Регистрация" in response.get_data(as_text=True)


def test_register_success(client):
    response = client.post(
        "/register",
        data={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password",
            "password2": "password",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Отлично, вы зарегистрированы!" in response.get_data(as_text=True)


def test_user_profile(logged_in_client):
    response = logged_in_client.get("/user/testuser")
    assert response.status_code == 200
    assert "Настройки профиля" in response.get_data(as_text=True)


def test_user_profile_wrong_user(logged_in_client):
    response = logged_in_client.get("/user/otheruser")
    assert response.status_code == 302  # Redirect to own profile


def test_edit_profile(logged_in_client):
    response = logged_in_client.post(
        "/edit_profile",
        data={
            "default_region_code": "01",
            "default_carrier_id": "1234",
            "default_unit_id": "5678",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Настройки профиля для массовой генерации успешно сохранены" in response.get_data(as_text=True)


def test_route_list(logged_in_client):
    response = logged_in_client.get("/routes")
    assert response.status_code == 200
    assert "routes" in response.get_data(as_text=True) or "Маршруты" in response.get_data(as_text=True)  # Assuming template has this


def test_create_route_info_get(logged_in_client):
    response = logged_in_client.get("/route/edit/info")
    assert response.status_code == 200
    assert "Создание маршрута" in response.get_data(as_text=True)


def test_create_route_info_post(logged_in_client):
    response = logged_in_client.post(
        "/route/edit/info",
        data={
            "route_name": "Test Route",
            "transport_type": "bus",
            "carrier_id": "1234",
            "unit_id": "5678",
            "route_number": "001",
            "region_code": "01",
            "decimal_places": "2",
            "tariff_tables-0-tariff_name": "Tariff 1",
            "tariff_tables-0-table_type_code": "02",
            "tariff_tables-0-ss_series_codes": "A;B",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Check if redirected to stops


def test_edit_route_stops(logged_in_client):
    # First create a route
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,  # Assuming test_user id is 1
            route_name="Test",
            transport_type="bus",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.get(f"/route/edit/{route_id}/stops")
    assert response.status_code == 200


def test_edit_route_prices(logged_in_client):
    # Similar, create route with stops_set=True
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="bus",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}, {"name": "Stop2", "km": "10"}],
            price_matrix=[],
            tariff_tables=[],
            stops_set=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.get(f"/route/edit/{route_id}/prices")
    assert response.status_code == 200


def test_delete_route(logged_in_client):
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="bus",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
            is_completed=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(f"/route/delete/{route_id}", follow_redirects=True)
    assert response.status_code == 200
    assert "успешно удален" in response.get_data(as_text=True)


def test_generate_config_incomplete_route(logged_in_client):
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="bus",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
            is_completed=False,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.get(f"/route/{route_id}/generate_config")
    assert response.status_code == 302  # Redirect to edit stops


def test_generate_bulk_config(logged_in_client):
    # Create a completed route
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="bus",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}],
            price_matrix=[[{"1": 10.0}]],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "T1",
                    "table_type_code": "02",
                    "ss_series_codes": "A",
                    "parsed_ss_codes_list": ["A"],
                }
            ],
            is_completed=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(
        "/routes/generate_bulk_config",
        data={
            "route_ids": [str(route_id)],
            "region_code": "01",
            "carrier_id": "1234",
            "unit_id": "5678",
            "decimal_places": "2",
        },
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"


def test_import_route_get(logged_in_client):
    response = logged_in_client.get("/route/import")
    assert response.status_code == 200
    assert "Импорт маршрута" in response.get_data(as_text=True)  # Assuming template has this


def test_create_route_info_post_invalid_data(logged_in_client):
    response = logged_in_client.post(
        "/route/edit/info",
        data={
            "route_name": "",  # Invalid: empty
            "transport_type": "0x02",
            "carrier_id": "1234",
            "unit_id": "5678",
            "route_number": "001",
            "region_code": "01",
            "decimal_places": "2",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Создание маршрута" in response.get_data(as_text=True)  # Should stay on form


def test_edit_route_stops_post_valid(logged_in_client):
    # First create a route
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x20",  # Non-city route
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(
        f"/route/edit/{route_id}/stops",
        data={
            "stops-0-stop_name": "Stop 1",
            "stops-0-km_distance": "0.00",
            "stops-1-stop_name": "Stop 2",
            "stops-1-km_distance": "10.50",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Check if redirected to prices


def test_edit_route_stops_post_invalid(logged_in_client):
    # First create a route
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x20",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(
        f"/route/edit/{route_id}/stops",
        data={
            "stops-0-stop_name": "Stop 1",
            "stops-0-km_distance": "5.00",  # Invalid: not 0
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Остановки" in response.get_data(as_text=True)  # Should stay on form


def test_edit_route_prices_post_valid(logged_in_client):
    # Create route with stops set
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}],
            price_matrix=[],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "T1",
                    "table_type_code": "02",
                    "ss_series_codes": "A",
                    "parsed_ss_codes_list": ["A"],
                }
            ],
            stops_set=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(
        f"/route/edit/{route_id}/prices",
        data={
            "price_matrix_data": '{"0":{"0":{"1":"10.00"}}}',  # JSON data
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_edit_route_prices_post_invalid_json(logged_in_client):
    # Create route with stops set
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}],
            price_matrix=[],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "T1",
                    "table_type_code": "02",
                    "ss_series_codes": "A",
                    "parsed_ss_codes_list": ["A"],
                }
            ],
            stops_set=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(
        f"/route/edit/{route_id}/prices",
        data={
            "price_matrix_data": "invalid json",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Should handle JSON parsing error gracefully


def test_generate_config_completed_route(logged_in_client):
    # Create a completed route
    with logged_in_client.application.app_context():
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}],
            price_matrix=[[{"1": 10.0}]],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "T1",
                    "table_type_code": "02",
                    "ss_series_codes": "A",
                    "parsed_ss_codes_list": ["A"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.get(f"/route/{route_id}/generate_config")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"


def test_generate_config_not_owner(logged_in_client):
    # Create route for different user
    with logged_in_client.application.app_context():
        route = Route(
            user_id=999,  # Different user
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[{"name": "Stop1", "km": "0"}],
            price_matrix=[[{"1": 10.0}]],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "T1",
                    "table_type_code": "02",
                    "ss_series_codes": "A",
                    "parsed_ss_codes_list": ["A"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.get(f"/route/{route_id}/generate_config")
    assert response.status_code == 302  # Redirect to route_list
    assert "/routes" in response.headers["Location"]


def test_delete_route_not_owner(logged_in_client):
    with logged_in_client.application.app_context():
        route = Route(
            user_id=999,  # Different user
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places=2,
            stops=[],
            price_matrix=[],
            tariff_tables=[],
            is_completed=True,
        )
        db.session.add(route)
        db.session.commit()
        route_id = route.id

    response = logged_in_client.post(f"/route/delete/{route_id}", follow_redirects=True)
    assert response.status_code == 200
    # Check that route still exists
    route_after = db.session.get(Route, route_id)
    assert route_after is not None


def test_edit_profile_post_invalid(logged_in_client):
    response = logged_in_client.post(
        "/edit_profile",
        data={
            "default_region_code": "abc",  # Invalid
            "default_carrier_id": "1234",
            "default_unit_id": "5678",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Настройки профиля" in response.get_data(as_text=True)  # Should stay on form


def test_register_post_invalid_email(client):
    response = client.post(
        "/register",
        data={
            "username": "newuser",
            "email": "invalid-email",  # Invalid
            "password": "password",
            "password2": "password",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Регистрация" in response.get_data(as_text=True)  # Should stay on form


def test_login_post_invalid_credentials(logged_in_client):
    # Logout first
    logged_in_client.get("/logout")

    response = logged_in_client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "wrongpassword",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Неверный логин или пароль" in response.get_data(as_text=True)


def test_import_route_post_valid_file(logged_in_client):
    # Mock a valid config file content
    config_content = """H;01;1234;5678;2
R;001;02;1;Test Route;1
0;0.00;Stop1
1;02;A
0;0;100
"""

    # Create a temporary file
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(config_content)
        temp_file_path = f.name

    try:
        with open(temp_file_path, "rb") as f:
            file_data = f.read()

        response = logged_in_client.post(
            "/route/import",
            data={
                "route_file": (file_data, "config.txt"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code == 200
    finally:
        os.unlink(temp_file_path)


def test_import_route_post_invalid_file(logged_in_client):
    response = logged_in_client.post(
        "/route/import",
        data={
            "route_file": (b"invalid content", "config.jpg"),  # Wrong extension
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Импорт маршрута" in response.get_data(as_text=True)  # Should stay on form


def test_bulk_generate_config_no_routes(logged_in_client):
    response = logged_in_client.post(
        "/routes/generate_bulk_config",
        data={
            "route_ids": [],
            "region_code": "01",
            "carrier_id": "1234",
            "unit_id": "5678",
            "decimal_places": "2",
        },
    )
    assert response.status_code == 302  # Redirect to route_list


def test_bulk_generate_config_invalid_route_ids(logged_in_client):
    response = logged_in_client.post(
        "/routes/generate_bulk_config",
        data={
            "route_ids": ["999"],  # Non-existent route
            "region_code": "01",
            "carrier_id": "1234",
            "unit_id": "5678",
            "decimal_places": "2",
        },
    )
    assert response.status_code == 302  # Redirect to route_list
