import decimal


def prepare_data(data: dict):
    for k, v in data.items():
        if isinstance(v, decimal.Decimal):
            data[k] = str(v)
    return data
