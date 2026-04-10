from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MONSTERBORG_MODEL_REVISION = "monsterborg-reference-r3"


@dataclass(frozen=True, slots=True)
class MonsterBorgDimensions:
    model_revision: str
    wheel_diameter_m: float
    wheel_radius_m: float
    wheel_width_m: float
    motor_can_diameter_m: float
    motor_can_length_m: float
    chassis_length_m: float
    chassis_width_m: float
    chassis_thickness_m: float
    wheelbase_m: float
    track_width_m: float
    body_clearance_z_m: float
    wheel_center_z_m: float
    camera_mount_translation: tuple[float, float, float]
    camera_mount_pitch_rad: float
    range_mount_translation: tuple[float, float, float]
    imu_translation: tuple[float, float, float]
    body_mass_kg: float
    wheel_mass_kg: float
    footprint_radius_m: float
    dimension_source_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def monsterborg_dimensions() -> MonsterBorgDimensions:
    return MonsterBorgDimensions(
        model_revision=MONSTERBORG_MODEL_REVISION,
        wheel_diameter_m=0.105,
        wheel_radius_m=0.0525,
        wheel_width_m=0.038,
        motor_can_diameter_m=0.037,
        motor_can_length_m=0.057,
        chassis_length_m=0.160,
        chassis_width_m=0.140,
        chassis_thickness_m=0.003,
        wheelbase_m=0.132,
        track_width_m=0.198,
        body_clearance_z_m=0.027,
        wheel_center_z_m=0.0525,
        camera_mount_translation=(0.118, 0.0, 0.098),
        camera_mount_pitch_rad=0.17,
        range_mount_translation=(0.128, 0.0, 0.060),
        imu_translation=(0.0, 0.0, 0.060),
        body_mass_kg=1.70,
        wheel_mass_kg=0.10,
        footprint_radius_m=0.158,
        dimension_source_summary={
            "primary_sources": [
                "official-piborg-monsterborg",
                "official-pimoroni-monsterborg",
            ],
            "secondary_sources": [
                "formula-pi-monsterborg-camera-geometry",
            ],
            "visual_reference": "project/scenarios/ders_cizim/worlds/monsterborg.wbt",
            "resolved_dimensions": {
                "wheel_diameter_m": 0.105,
                "motor_can_diameter_m": 0.037,
                "chassis_thickness_m": 0.003,
                "chassis_length_m": 0.160,
                "chassis_width_m": 0.140,
                "wheel_width_m": 0.038,
                "wheelbase_m": 0.132,
                "track_width_m": 0.198,
            },
        },
    )
