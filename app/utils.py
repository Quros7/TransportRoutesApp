def write_route_body_to_buffer(buffer, route, decimal_places_for_config):
    """
    Записывает информацию о маршруте (начиная с тега R) в переданный буфер, используя указанную точность цен.
    Кодировка CP866.
    """
    def write_line(text):
        buffer.write((text + '\r\n').encode('cp866', errors='replace'))

    # ==========================================
    # 2. ОПИСАНИЕ МАРШРУТА (Тэг R)
    # ==========================================
    route_id_str = str(route.route_number)[:6]
    trans_type = route.transport_type.replace('0x', '')
    zones_count = len(route.stops)
    route_name = route.route_name[:30]
    tabs_count = len(route.tariff_tables)

    r_line = f"R;{route_id_str};{trans_type};{zones_count};{route_name};{tabs_count}"
    write_line(r_line)

    # ==========================================
    # 3. СПИСОК ОСТАНОВОК (ЗОН)
    # ==========================================
    for i, stop in enumerate(route.stops):
        zone_no = str(i)
        km_val = stop['km']
        zone_name = stop['name'][:19]
        s_line = f"{zone_no};{km_val};{zone_name}"
        write_line(s_line)

    # ==========================================
    # 4. ТАРИФНЫЕ ТАБЛИЦЫ (Tabs)
    # ==========================================
    for table in route.tariff_tables:
        tab_n = table['tab_number']
        ss_codes = table['ss_series_codes']
        t_line = f"{tab_n};{table['table_type_code']};{ss_codes}"
        write_line(t_line)

    # ==========================================
    # 5. МАТРИЦА ЦЕН
    # ==========================================
    # ИСПОЛЬЗУЕМ ПЕРЕДАННЫЙ ПАРАМЕТР ТОЧНОСТИ 
    multiplier = 10 ** int(decimal_places_for_config)

    zones_count = len(route.stops)

    for i in range(zones_count):
        for j in range(zones_count):
            if j >= i:
                prices_list = []
                for table in route.tariff_tables:
                    tab_id_str = str(table['tab_number'])
                    try:
                        raw_price = route.price_matrix[i][j].get(tab_id_str, 0)
                        
                        # ПРЕОБРАЗОВАНИЕ В ЦЕЛОЕ ЧИСЛО С УЧЕТОМ НОВОГО МНОЖИТЕЛЯ
                        price_int = int(float(raw_price) * multiplier)
                        prices_list.append(str(price_int))
                    except (IndexError, AttributeError, ValueError):
                        prices_list.append("0")
                
                prices_str = ";".join(prices_list)
                m_line = f"{i};{j};{prices_str}"
                write_line(m_line)
