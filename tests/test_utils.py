import io

from app.models import Route
from app.utils import normalize_for_cp866, write_route_body_to_buffer


class TestNormalizeForCp866:
    def test_normalize_empty_string(self):
        assert normalize_for_cp866("") == ""

    def test_normalize_none(self):
        assert normalize_for_cp866(None) == ""

    def test_normalize_special_characters(self):
        text = "Тест — «кавычки» №1"
        result = normalize_for_cp866(text)
        assert "—" not in result
        assert "«" not in result
        assert "»" not in result
        assert "№" not in result
        assert "-" in result
        assert '"' in result
        assert "No" in result

    def test_normalize_multiple_replacements(self):
        text = "—–«»„“№"
        result = normalize_for_cp866(text)
        assert result == '--""""No'


class TestWriteRouteBodyToBuffer:
    def test_write_route_body_complete_route(self):
        # Create a mock route with all necessary data
        route = Route(
            user_id=1,
            route_name="Test Route",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places="2",
            stops=[
                {"name": "Stop1", "km": "0.00"},
                {"name": "Stop2", "km": "10.50"},
            ],
            price_matrix=[
                [{"1": 10.0}, {"1": 15.0}],
                [None, {"1": 20.0}],
            ],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "Tariff1",
                    "table_type_code": "02",
                    "ss_series_codes": "01;02",
                    "parsed_ss_codes_list": ["01", "02"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )

        buffer = io.BytesIO()
        write_route_body_to_buffer(buffer, route, "2")

        content = buffer.getvalue().decode("cp866", errors="replace")
        lines = content.strip().split("\r\n")

        # Check R line
        assert lines[0].startswith("R;001;02;2;Test Route;1")

        # Check stops
        assert "0;0.00;Stop1" in lines
        assert "1;10.50;Stop2" in lines

        # Check tariff tables
        assert "1;02;01;02" in lines

        # Check price matrix
        price_lines = [line for line in lines if line.startswith("0;") or line.startswith("1;")]
        assert len(price_lines) >= 3  # At least 0-0, 0-1, 1-1

    def test_write_route_body_with_unicode_chars(self):
        route = Route(
            user_id=1,
            route_name="Тест — маршрут",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places="2",
            stops=[{"name": "Остановка №1", "km": "0.00"}],
            price_matrix=[[{"1": 10.0}]],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "Тариф",
                    "table_type_code": "02",
                    "ss_series_codes": "01",
                    "parsed_ss_codes_list": ["01"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )

        buffer = io.BytesIO()
        write_route_body_to_buffer(buffer, route, "2")

        content = buffer.getvalue().decode("cp866", errors="replace")
        # Check that special chars are normalized
        assert "—" not in content
        assert "№" not in content

    def test_write_route_body_different_decimal_places(self):
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places="2",
            stops=[{"name": "Stop1", "km": "0.00"}],
            price_matrix=[[{"1": 12.34}]],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "Tariff",
                    "table_type_code": "02",
                    "ss_series_codes": "01",
                    "parsed_ss_codes_list": ["01"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )

        buffer = io.BytesIO()
        write_route_body_to_buffer(buffer, route, "1")  # 1 decimal place

        content = buffer.getvalue().decode("cp866", errors="replace")
        lines = content.strip().split("\r\n")

        # Find the price line
        price_line = None
        for line in lines:
            if line.startswith("0;0;"):
                price_line = line
                break

        assert price_line is not None
        # 12.34 * 10^1 = 123.4 -> int(123.4) = 123
        assert price_line == "0;0;123"

    def test_write_route_body_missing_price_data(self):
        route = Route(
            user_id=1,
            route_name="Test",
            transport_type="0x02",
            carrier_id="1234",
            unit_id="5678",
            route_number="001",
            region_code="01",
            decimal_places="2",
            stops=[
                {"name": "Stop1", "km": "0.00"},
                {"name": "Stop2", "km": "10.00"},
            ],
            price_matrix=[
                [{}],  # Missing price data
                [None, {}],
            ],
            tariff_tables=[
                {
                    "tab_number": 1,
                    "tariff_name": "Tariff",
                    "table_type_code": "02",
                    "ss_series_codes": "01",
                    "parsed_ss_codes_list": ["01"],
                }
            ],
            stops_set=True,
            is_completed=True,
        )

        buffer = io.BytesIO()
        write_route_body_to_buffer(buffer, route, "2")

        content = buffer.getvalue().decode("cp866", errors="replace")
        lines = content.strip().split("\r\n")

        # Check that missing prices default to 0
        price_lines = [line for line in lines if ";" in line and line[0].isdigit() and line[2] == ";"]
        for line in price_lines:
            parts = line.split(";")
            if len(parts) >= 3:
                prices = parts[2:]
                assert all(price == "0" for price in prices)
