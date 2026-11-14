"""Central configuration and layout parameters for The Drowned Sanctuary."""

from typing import Dict


SEED = 42

# Quality presets controlling geometry subdivision, masonry count, and render settings
QUALITY_PRESETS: Dict[str, dict] = {
    "preview": {
        "geometry_preset": "fast",
        "res_x": 960,
        "res_y": 540,
        "samples": 48,
        "adaptive_threshold": 0.03,
        "use_denoising": True,
        "volume_step_rate": 2.2,
        "volume_max_steps": 64,
        "max_bounces": 6,
        "diffuse_bounces": 2,
        "glossy_bounces": 3,
        "transmission_bounces": 4,
        "volume_bounces": 0,
        "subsurf_level": 1,
        "terrain_subdiv": 92,
        "cliff_subdiv": 88,
        "root_bevel_res": 3,
        "rubble_scale": 1.0,
        "output_filename": "preview.png",
    },
    "review": {
        "geometry_preset": "balanced",
        "res_x": 1920,
        "res_y": 1080,
        "samples": 128,
        "adaptive_threshold": 0.02,
        "use_denoising": True,
        "volume_step_rate": 1.5,
        "volume_max_steps": 128,
        "max_bounces": 8,
        "diffuse_bounces": 3,
        "glossy_bounces": 4,
        "transmission_bounces": 6,
        "volume_bounces": 1,
        "subsurf_level": 2,
        "terrain_subdiv": 110,
        "cliff_subdiv": 72,
        "root_bevel_res": 4,
        "rubble_scale": 1.0,
        "output_filename": "review.png",
    },
    "final": {
        "geometry_preset": "high",
        "res_x": 2560,
        "res_y": 1440,
        "samples": 128,  # Adjusted for CPU-only hardware (12th Gen Intel i7-1265U) + OpenImageDenoise
        "adaptive_threshold": 0.02,
        "use_denoising": True,
        "volume_step_rate": 1.8,
        "volume_max_steps": 96,
        "max_bounces": 6,
        "diffuse_bounces": 2,
        "glossy_bounces": 3,
        "transmission_bounces": 4,
        "volume_bounces": 0,
        "subsurf_level": 2,
        "terrain_subdiv": 120,
        "cliff_subdiv": 96,
        "root_bevel_res": 5,
        "rubble_scale": 1.25,
        "output_filename": "drowned_sanctuary_final.png",
    },
}

GEOMETRY_OVERRIDES: Dict[str, dict] = {
    "fast": {
        "subsurf_level": 1,
        "terrain_subdiv": 72,
        "cliff_subdiv": 48,
        "root_bevel_res": 3,
        "rubble_scale": 0.8,
    },
    "balanced": {
        "subsurf_level": 2,
        "terrain_subdiv": 108,
        "cliff_subdiv": 68,
        "root_bevel_res": 4,
        "rubble_scale": 1.0,
    },
    "high": {
        "subsurf_level": 2,
        "terrain_subdiv": 130,
        "cliff_subdiv": 84,
        "root_bevel_res": 5,
        "rubble_scale": 1.25,
    },
}


# Core color palette calibrated to sanctuary_reference.png (linear RGB)
COLORS = {
    "limestone_sunlit": (0.395, 0.352, 0.258, 1.0),   # #A9A18B sunlit limestone
    "limestone_mid": (0.200, 0.188, 0.148, 1.0),      # #817D70 midtone stone
    "limestone_shadow": (0.072, 0.082, 0.074, 1.0),   # #565C56 shadowed limestone
    "limestone_eroded": (0.165, 0.170, 0.138, 1.0),   # #77796D eroded stone
    "moss_olive": (0.068, 0.092, 0.040, 1.0),
    "moss_dark": (0.032, 0.048, 0.024, 1.0),
    "cliff_rock": (0.140, 0.135, 0.115, 1.0),
    "cliff_dark": (0.042, 0.048, 0.045, 1.0),
    "bark_ancient": (0.048, 0.038, 0.028, 1.0),
    "water_deep": (0.004, 0.012, 0.011, 1.0),
    "water_shallow": (0.009, 0.022, 0.019, 1.0),
    "statue_stone": (0.155, 0.160, 0.135, 1.0),
    "grass_muted": (0.062, 0.078, 0.034, 1.0),
    "mud_dark": (0.028, 0.030, 0.024, 1.0),
}


# World spatial layout (metric scale, Z=0 is water level)
LAYOUT = {
    "water_level": 0.0,
    "courtyard": {
        "center": (0.0, 2.0, 0.0),
        "ring_radius": 13.6,
        "ring_width": 1.35,
        "ring_height": 0.45,
        "island_radius": 4.2,
        "island_height": 0.52,
        "floor_z": -0.45,
    },
    "statue": {
        "location": (0.0, 2.0, 0.0),
        "rotation_z_deg": -16.0,
        "pedestal_height": 4.0,
        "figure_height": 14.8,
    },
    "causeway": {
        "start_xy": (0.0, -78.0),
        "end_xy": (0.0, -11.4),
        "width": 3.25,
        "base_z": -2.5,
        "top_z": 0.42,
        "figure_y": -42.5,
    },
    "towers": {
        "left_front": {
            "location": (-21.0, -2.5, -2.0),
            "rotation_z_deg": 4.0,
            "width": 9.8,
            "depth": 9.8,
            "base_height": 19.5,
            "belfry_height": 12.8,
        },
        "left_rear": {
            "location": (-14.5, 22.0, -2.0),
            "rotation_z_deg": 0.0,
            "width": 7.4,
            "depth": 7.4,
            "base_height": 23.5,
            "belfry_height": 17.5,
        },
        "right_rear": {
            "location": (11.2, 22.5, -2.0),
            "rotation_z_deg": 0.0,
            "width": 7.4,
            "depth": 7.4,
            "base_height": 22.5,
            "belfry_height": 17.0,
        },
        "right_front": {
            "location": (26.5, -9.5, -2.0),
            "rotation_z_deg": -8.0,
            "width": 10.6,
            "depth": 10.6,
            "base_height": 20.5,
            "belfry_height": 17.5,
        },
        "left_bastion": {
            "location": (-51.0, 9.5, -1.0),
            "rotation_z_deg": 14.0,
            "width": 7.4,
            "depth": 7.4,
            "height": 22.5,
        },
        "distant_spire": {
            "location": (45.0, 150.0, -2.0),
            "rotation_z_deg": -15.0,
            "width": 6.8,
            "depth": 6.8,
            "height": 34.0,
        },
    },
    "rear_arcade": {
        "center": (0.0, 12.5, -2.0),
        "radius": 16.0,
        "start_angle_deg": 146.0,
        "end_angle_deg": 34.0,
        "bays": 6,
        "pier_height": 13.5,
        "arch_apex_height": 18.0,
        "wall_top_height": 22.2,
    },
    "cameras": {
        "CAM_HERO_REFERENCE": {
            "location": (30.0, -104.0, 41.0),
            "target": (-1.5, 6.5, 7.6),
            "lens": 33.5,
            "sensor_width": 36.0,
            "dof_enable": False,
        },
        "CAM_ARCHITECTURE_DETAIL": {
            "location": (5.0, -45.0, 16.0),
            "target": (20.0, -6.0, 21.0),
            "lens": 45.0,
            "sensor_width": 36.0,
            "dof_enable": False,
        },
        "CAM_STATUE_COURTYARD": {
            "location": (8.0, -26.0, 7.5),
            "target": (0.0, 2.0, 9.0),
            "lens": 42.0,
            "sensor_width": 36.0,
            "dof_enable": False,
        },
        "CAM_WATER_APPROACH": {
            "location": (-4.5, -62.0, 3.8),
            "target": (0.0, 2.0, 12.0),
            "lens": 35.0,
            "sensor_width": 36.0,
            "dof_enable": False,
        },
    },
    "lighting": {
        # High physical sun energy vs moody overcast sky produces crisp warm highlights & cool shadows
        "sun_elevation_deg": 21.5,
        "sun_azimuth_deg": 84.0,
        "sky_glow_azimuth_deg": 54.0,
        "sun_energy": 24.0,
        "sun_angle_deg": 3.2,
        "sun_color": (1.0, 0.80, 0.52),
        "sky_strength": 0.24,
        "air_density": 1.15,
        "aerosol_density": 2.0,
        "ozone_density": 1.15,
    },
    "atmosphere": {
        "mist_density": 0.024,
        "courtyard_haze_density": 0.016,
        "distant_haze_density": 0.0068,
    },
}
