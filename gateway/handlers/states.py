from typing import Union, Optional, Dict, Any


def generate_mem3dg_state(
        characteristic_time_step: float,
        tension_modulus: float,
        preferred_area: float,
        preferred_volume: float,
        reservoir_volume: float,
        osmotic_strength: float,
        volume: float,
        parameters_config: dict[str, float | int],
        damping: float,
        tolerance: Optional[float] = 1e-11,
        geometry_type: Optional[str] = None,
        geometry_parameters: Optional[Dict[str, Union[float, int]]] = None,
        mesh_file: Optional[str] = None,
) -> Dict[str, Any]:
    doc = {
        'membrane': {
            '_type': 'process',
            'address': 'local:simple-membrane-process',
            'config': {
                'characteristic_time_step': characteristic_time_step,
                'tension_model': {
                    'modulus': tension_modulus,
                    'preferred_area': preferred_area
                },
                'osmotic_model': {
                    'preferred_volume': preferred_volume,
                    'reservoir_volume': reservoir_volume,
                    'strength': osmotic_strength,
                    'volume': volume
                },
                'parameters': {
                    'damping': damping
                },
                'tolerance': tolerance,
                'console_output': False
            },
            'inputs': {
                'geometry': ['geometry_store'],
                'velocities': ['velocities_store'],
                'protein_density': ['protein_density_store'],
                'volume': ['volume_store'],
                'preferred_volume': ['preferred_volume_store'],
                'reservoir_volume': ['reservoir_volume_store'],
                'surface_area': ['surface_area_store'],
                'osmotic_strength': ['osmotic_strength_store'],
            },
            'outputs': {
                'geometry': ['geometry_store'],
                'velocities': ['velocities_store'],
                'protein_density': ['protein_density_store'],
                'volume': ['volume_store'],
                'preferred_volume': ['preferred_volume_store'],
                'reservoir_volume': ['reservoir_volume_store'],
                'surface_area': ['surface_area_store'],
                'net_forces': ['net_forces_store'],
                'notable_vertices': ['notable_vertices_store']
            }
        },
        'emitter': {
            '_type': 'step',
            'address': 'local:ram-emitter',
            'config': {
                'emit': {
                    'geometry': 'GeometryType',
                    'velocities': 'VelocitiesType',
                    'protein_density': 'ProteinDensityType',
                    'volume': 'float',
                    'preferred_volume': 'float',
                    'reservoir_volume': 'float',
                    'surface_area': 'float',
                    'net_forces': 'MechanicalForcesType',
                    'notable_vertices': 'list[boolean]',
                }
            },
            'inputs': {
                'geometry': ['geometry_store'],
                'velocities': ['velocities_store'],
                'protein_density': ['protein_density_store'],
                'volume': ['volume_store'],
                'preferred_volume': ['preferred_volume_store'],
                'reservoir_volume': ['reservoir_volume_store'],
                'surface_area': ['surface_area_store'],
                'net_forces': ['net_forces_store'],
                'notable_vertices': ['notable_vertices_store'],
            }
        }
    }

    for key, value in parameters_config.items():
        doc['membrane']['config']['parameters'][key] = value

    if geometry_parameters is not None and geometry_type is not None:
        doc['membrane']['config']['geometry'] = {
            'type': geometry_type,
            'parameters': geometry_parameters
        }
    else:
        doc['membrane']['config']['mesh_file'] = mesh_file

    return doc

