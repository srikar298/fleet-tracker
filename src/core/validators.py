from abc import ABC, abstractmethod
from typing import Any


class ValidationRule(ABC):
    @abstractmethod
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        """Returns (is_valid, flag_message). If is_valid is False, it's flagged."""
        pass


class ZeroDistanceRule(ValidationRule):
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        distance = float(trip_data.get("distance", 0))
        if distance < 1:
            return False, "Zero/Low Distance"
        return True, ""


class DistanceOutlierRule(ValidationRule):
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        distance = float(trip_data.get("distance", 0))
        if distance > 400:
            return False, "Distance Outlier"
        return True, ""


class SpeedRule(ValidationRule):
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        duration_mins = float(trip_data.get("duration_mins", 0))
        distance = float(trip_data.get("distance", 0))
        if duration_mins > 0 and distance > 0:
            avg_speed = distance / (duration_mins / 60)
            if avg_speed > 80:
                return False, "Too Fast"
        return True, ""


class MileageRule(ValidationRule):
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        mileage = float(trip_data.get("mileage", 0))
        if mileage > 0 and (mileage < 8 or mileage > 25):
            return False, "Mileage Issue"
        return True, ""


class FinancialIntegrityRule(ValidationRule):
    def validate(self, trip_data: dict[str, Any]) -> tuple[bool, str]:
        fuel_cost = float(trip_data.get("fuel_cost", 0))
        revenue = float(trip_data.get("revenue", 0))
        if fuel_cost > revenue:
            return False, "Negative Margin"
        return True, ""


class TripValidator:
    def __init__(self) -> None:
        self.rules: list[ValidationRule] = [
            ZeroDistanceRule(),
            DistanceOutlierRule(),
            SpeedRule(),
            MileageRule(),
            FinancialIntegrityRule(),
        ]

    def evaluate_trip(self, trip_data: dict[str, Any]) -> tuple[list[str], int]:
        """Runs all rules. Returns (List of flags, driver_score)"""
        flags: list[str] = []
        for rule in self.rules:
            is_valid, message = rule.validate(trip_data)
            if not is_valid:
                flags.append(message)

        # Base score 100
        penalty_flags = [f for f in flags if f != "Negative Margin"]
        score = 100 - (len(penalty_flags) * 15)

        if "Negative Margin" in flags:
            score -= 20

        return flags, max(0, score)
