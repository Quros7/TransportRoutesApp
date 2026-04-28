import uuid


class TRFZRouteImporter:
    def __init__(self, raw_data):
        self.raw_data = raw_data
        self.lines = []
        self._prepare_lines()

    def _prepare_lines(self):
        """Декодирует и очищает строки"""
        try:
            content = self.raw_data.decode("utf-8")
        except UnicodeDecodeError:
            content = self.raw_data.decode("cp866", errors="replace")
        
        self.lines = [line.strip() for line in content.splitlines() if line.strip()]

    def get_formatted_route_data(self):
        """
        Главный метод, который возвращает список словарей 
        с данными для создания объектов Route.
        """
        if len(self.lines) < 2:
            raise ValueError("Файл слишком короткий")

        header = self.lines[0].split(";")
        if len(header) < 5:
            raise ValueError("Неверный заголовок TRFZ")

        
        multiplier = 10**int(header[4])

        route_indices = [i for i, line in enumerate(self.lines) if line.startswith("R;")]
        all_routes = []

        for i, start_idx in enumerate(route_indices):
            end_idx = route_indices[i+1] if i + 1 < len(route_indices) else len(self.lines)
            block = self.lines[start_idx:end_idx]

            r_line = block[0].split(";")
            if len(r_line) < 6: continue

            zones_count = int(r_line[3])
            tabs_count = int(r_line[5])

            # Парсим остановки
            stops = []
            for sl in block[1 : 1 + zones_count]:
                parts = sl.split(";")
                if len(parts) >= 3:
                    stops.append({"name": parts[2], "km": parts[1]})

            # Парсим тарифы
            tabs_start = 1 + zones_count
            tab_lines = block[tabs_start : tabs_start + tabs_count]
            tariff_tables = []
            # Список UID в порядке их следования в файле для сопоставления с матрицей
            ordered_uids = []

            for idx, tl in enumerate(tab_lines, start=1):
                parts = tl.split(";")
                if len(parts) < 2: continue

                # Генерируем уникальный ID для этой таблицы
                new_uid = f"t{uuid.uuid4().hex[:8]}" 
                ss_list = [c.strip() for c in parts[2:] if c.strip()]
                
                tariff_tables.append({
                    "uid": new_uid,
                    "tariff_name": f"Тариф {idx}",
                    "table_type_code": parts[1],
                    "ss_series_codes": ";".join(ss_list),
                })
                ordered_uids.append(str(new_uid))

            # Парсим матрицу
            matrix = [[{} for _ in range(zones_count)] for _ in range(zones_count)]
            price_lines = block[tabs_start + tabs_count :]
            for ml in price_lines:
                parts = ml.split(";")
                if len(parts) < 3: continue
                try:
                    r_idx, c_idx = int(parts[0]), int(parts[1])
                    prices = parts[2:]

                    # Сопоставляем цену из колонки с соответствующим UID из списка ordered_uids
                    cell_data = {}
                    for p_idx, p_val in enumerate(prices):
                        if p_idx < len(ordered_uids):
                            target_uid = ordered_uids[p_idx]
                            cell_data[target_uid] = float(p_val) / multiplier
                    
                    if r_idx < zones_count and c_idx < zones_count:
                        matrix[r_idx][c_idx] = cell_data
                except: continue

            # Формируем итоговый объект для этого маршрута
            all_routes.append({
                "common": {
                    "region_code": header[0],
                    "carrier_id": header[1],
                    "unit_id": header[2],
                    "decimal_places": str(header[4])
                },
                "route_info": {
                    "route_number": r_line[1],
                    "route_name": r_line[4].strip(),
                    "transport_type": f"0x{r_line[2]}" if not r_line[2].startswith("0x") else r_line[2],
                },
                "stops": stops,
                "tariff_tables": tariff_tables,
                "price_matrix": matrix
            })

        return all_routes
