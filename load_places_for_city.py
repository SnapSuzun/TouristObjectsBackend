import DataLoader

data_loader = DataLoader.DataLoader()
# data_loader.load_places_for_city(city_id=777934, use_last_cursor=True)
DataLoader.DataLoader.search_places_for_city('5b01ac9aff93a20480b397a9', use_last_cursor=True)