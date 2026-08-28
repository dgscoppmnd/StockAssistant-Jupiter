import csv
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    pd = None


class SimpleDataFrame:
    def __init__(self, data):
        if isinstance(data, dict):
            columns = list(data.keys())
            rows = []
            length = len(next(iter(data.values()), []))
            for index in range(length):
                row = {column: data[column][index] for column in columns}
                rows.append(row)
            self._rows = rows
            self.columns = columns
        else:
            self._rows = list(data)
            self.columns = list(self._rows[0].keys()) if self._rows else []

    @property
    def empty(self):
        return len(self._rows) == 0

    def to_csv(self, path, index=False):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns)
            writer.writeheader()
            writer.writerows(self._rows)


def DataFrame(data):
    if pd is not None:
        return pd.DataFrame(data)
    return SimpleDataFrame(data)
