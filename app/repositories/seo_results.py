import json
import os

from app.config import get_config
from app.exceptions import StorageError


def save_result(data: dict) -> None:
    results_file = get_config().results_file

    try:
        os.makedirs(os.path.dirname(results_file) or ".", exist_ok=True)

        if os.path.exists(results_file):
            with open(results_file, "r", encoding="utf-8") as file:
                raw_content = file.read().strip()

            if not raw_content:
                existing_data = []
            else:
                existing_data = json.loads(raw_content)
        else:
            existing_data = []

        if not isinstance(existing_data, list):
            raise StorageError("Stored SEO results must be a JSON array")

        existing_data.append(data)

        with open(results_file, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=2)
    except StorageError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise StorageError("Failed to save SEO result") from error
