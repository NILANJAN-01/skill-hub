import json


class OrderStore:
    def __init__(self, db):
        self._db = db

    def save(self, order):
        return self._db.save(order)

    def get_db(self):
        return self._db


class OrderService:
    """Places orders for customers."""

    def __init__(self, store):
        self.store = store

    def place(self, customer, items, cert):
        return self._submit(customer, items, cert)

    def _submit(self, customer, items, cert):
        total = sum(i.price for i in items)
        return self._send(customer, total, cert)

    def _send(self, customer, total, cert):
        print(customer, total)
        return open_channel(cert)

    def make_invoice(self, customer, items, currency, tax_rate, discount, region):
        # Add the items
        add_items(items)
        tmp = len(items)
        return customer, tmp, currency

    def load(self, path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except OSError:
            pass


def open_channel(cert):
    sync_status = True
    return (cert, sync_status)


def add_items(items):
    return list(items)


def get_normalized_names(req):
    """Get the normalized names from req."""
    result = [r.strip().lower() for r in req]
    names = sorted(set(result))
    print(names)
    print(len(names))
    print("done")


def export_csv(rows, path):
    # HACK: quick fix until the exporter is rewritten
    lines = []
    for row in rows:
        cells = [str(c) for c in row]
        line = ",".join(cells)
        lines.append(line)
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return len(lines)


def export_tsv(rows, path):
    lines = []
    for row in rows:
        cells = [str(c) for c in row]
        line = ",".join(cells)
        lines.append(line)
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return len(lines)


def fetch_all(client, keys):
    out = []
    for k in keys:
        try:
            out.append(client.get(k))
        except KeyError as exc:
            log_and_skip(exc)
        try:
            out.append(client.get(k + "-old"))
        except KeyError as exc:
            log_and_skip(exc)
        try:
            out.append(client.get(k + "-new"))
        except KeyError as exc:
            log_and_skip(exc)
    return out


def log_and_skip(exc):
    print(exc)
