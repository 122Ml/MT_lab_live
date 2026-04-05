import json
from pathlib import Path

from app.schemas.translation import TestCaseItem


class TestCaseService:
    def __init__(self, file_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "data" / "test_cases.json"
        self.file_path = Path(file_path) if file_path else default_path

    def list_cases(self) -> list[TestCaseItem]:
        if not self.file_path.exists():
            return []
        with self.file_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        return [TestCaseItem.model_validate(item) for item in raw]

